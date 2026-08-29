import json
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from hashlib import sha256
from secrets import token_urlsafe

from pydantic_ai import Agent
from pydantic_ai.exceptions import (
    ModelHTTPError,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
    UserError,
)
from pydantic_ai.models.openai import (
    OpenAIResponsesModel,
    OpenAIResponsesModelSettings,
)
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import RunUsage, UsageLimits

from app.core.config import get_settings
from app.core.errors import (
    AIError,
    AIUnavailableError,
    InsightContextExpiredError,
    InsightUnavailableError,
    InvalidAnalysisFilterError,
)
from app.schemas.performance import (
    EmployeeKpiScores,
    KpiResult,
    PerformanceDataset,
    ValidationFinding,
)
from app.schemas.uploads import (
    AIInsightResponse,
    AnalysisFilters,
    AnalysisSummary,
    AnalyzeUploadResponse,
    EmployeeAIInsight,
    ImportIssue,
    MappingProposal,
    MappingValidation,
    UploadAnalysis,
    UploadCatalog,
)
from app.services import catalog
from app.services.datasets import build_performance_dataset
from app.services.imports import parse_upload
from app.services.performance import (
    build_performance_alerts,
    calculate_kpis,
    calculate_weekly_kpi_trends,
    inspect_dataset,
    summarize_validation,
    validate_dataset,
)

INSTRUCTIONS = """
You map uploaded employee-performance tables to the supplied canonical schema.

Use only the bounded workbook synopsis in the user prompt. Select tables and map columns by
their headers, inferred types, missing-value counts, and sample values; do not rely on a sheet
name alone. Return lower confidence when semantics are ambiguous. Map optional validation
fields, especially attendance actual_end, whenever the source supports them. Do not calculate,
validate source records, invent values, or explain scores. Return only the structured output.
"""

_MAPPING_CACHE_MAX_SIZE = 64
_mapping_cache: OrderedDict[str, UploadAnalysis] = OrderedDict()
_INSIGHT_CONTEXT_CACHE_MAX_SIZE = 32
_INSIGHT_CONTEXT_TTL = timedelta(minutes=15)


@dataclass(frozen=True, slots=True)
class InsightEmployeeContext:
    prompt_context: dict[str, object]
    allowed_record_ids: frozenset[str]


@dataclass(frozen=True, slots=True)
class CachedInsightContext:
    created_at: datetime
    employees: dict[str, InsightEmployeeContext]


_insight_context_cache: OrderedDict[str, CachedInsightContext] = OrderedDict()


analysis_agent = Agent[None, UploadAnalysis](
    name="employee_performance_agent",
    instructions=INSTRUCTIONS,
    deps_type=type(None),
    output_type=UploadAnalysis,
)

insights_agent = Agent[None, EmployeeAIInsight](
    name="employee_performance_insights_agent",
    instructions="""
You explain validated employee-performance findings and suggest constructive, low-risk next
steps. Use only the supplied calculated results and findings. Do not calculate, alter, or
repeat KPI numbers. Do not infer causes, intent, personality, or protected characteristics.
Do not recommend hiring, firing, promotion, compensation, discipline, or other high-impact
employment decisions. For Insufficient data results, recommend improving evidence coverage,
not performance action. Every explanation and recommendation must cite one or more record IDs
listed for that employee. Return no insight for an employee without a supported finding.
For a missing report submission date, tell the user to verify whether the report was submitted;
do not assume a submission occurred or instruct them to invent a date. Focus directly on the
findings and avoid generic statements about complete source coverage. Put citations only in
the structured record_ids fields. Never write record IDs, citation lists, or parenthetical
citations inside message text. Mention only findings supported by that statement's record_ids.
""",
    deps_type=type(None),
    output_type=EmployeeAIInsight,
)


@lru_cache
def get_model() -> OpenAIResponsesModel:
    """Return the configured model or raise when no API key is available."""
    settings = get_settings()
    if not settings.openai_api_key:
        raise AIUnavailableError("OPENAI_API_KEY is not set, so the agent cannot run.")

    return OpenAIResponsesModel(
        settings.openai_model,
        provider=OpenAIProvider(api_key=settings.openai_api_key),
    )


async def analyze_upload(
    file_name: str | None,
    contents: bytes,
    maximum_bytes: int,
    employee_id: str | None = None,
    team: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> AnalyzeUploadResponse:
    """Parse an upload and let the agent select and map relevant source tables."""
    if start_date and end_date and start_date > end_date:
        raise InvalidAnalysisFilterError(
            "start_date must be on or before end_date."
        )
    upload_catalog = parse_upload(file_name, contents, maximum_bytes)
    workbook_context = _build_workbook_context(upload_catalog)
    schema_fingerprint = _schema_fingerprint(upload_catalog)
    analysis = _get_cached_analysis(schema_fingerprint)
    mapping_cache_hit = analysis is not None
    usage = RunUsage()

    if analysis is None:
        try:
            analysis = await _run_mapping_agent(
                workbook_context,
                usage,
            )
            invalid_mappings = [
                validation
                for validation in catalog.validate_mappings(
                    upload_catalog,
                    analysis.mapping_proposals,
                )
                if not validation.valid
            ]
            if invalid_mappings:
                analysis = await _repair_mappings(
                    workbook_context,
                    analysis,
                    invalid_mappings,
                    usage,
                )
        except (
            ModelHTTPError,
            UnexpectedModelBehavior,
            UsageLimitExceeded,
            UserError,
        ) as exc:
            raise AIError(f"The model call failed: {exc}") from exc

        final_validations = catalog.validate_mappings(
            upload_catalog,
            analysis.mapping_proposals,
        )
        if final_validations and all(
            validation.valid for validation in final_validations
        ):
            _cache_analysis(schema_fingerprint, analysis)

    performance_dataset, mapping_issues = build_performance_dataset(
        upload_catalog,
        analysis.mapping_proposals,
    )
    validation_findings = validate_dataset(performance_dataset)
    overview = inspect_dataset(performance_dataset)
    available_teams = overview.teams
    if team and team.casefold() not in {value.casefold() for value in available_teams}:
        raise InvalidAnalysisFilterError(f"Unknown team '{team}'.")
    known_employee_ids = {
        employee.employee_id for employee in performance_dataset.employees
    }
    if employee_id and employee_id not in known_employee_ids:
        raise InvalidAnalysisFilterError(f"Unknown employee_id '{employee_id}'.")
    effective_start: date | None = None
    effective_end: date | None = None
    if start_date or end_date:
        effective_start = start_date or overview.date_start
        effective_end = end_date or overview.date_end
    kpi_results = calculate_kpis(
        performance_dataset,
        employee_id=employee_id,
        team=team,
        start_date=effective_start,
        end_date=effective_end,
        validation_findings=validation_findings,
    )
    import_issues = [
        ImportIssue(
            code="header_not_found",
            message="No row with at least two non-empty header values was found.",
            source_name=table.source_name,
        )
        for table in upload_catalog.tables
        if table.header_row is None
    ]
    import_issues.extend(mapping_issues)
    result_employee_ids = {kpi.employee_id for kpi in kpi_results}
    employee_by_id = {
        employee.employee_id: employee for employee in performance_dataset.employees
    }
    included_record_ids = {
        record_id
        for result in kpi_results
        for record_id in result.supporting_record_ids
    }
    scoped_findings = [
        finding
        for finding in validation_findings
        if (
            finding.employee_id in result_employee_ids
            and (
                not finding.record_ids
                or bool(set(finding.record_ids) & included_record_ids)
            )
        )
        or finding.employee_id not in known_employee_ids
    ]
    project_links = {
        project.project_id: project.evidence_link
        for project in performance_dataset.projects
        if project.evidence_link
    }
    employee_results = [
        EmployeeKpiScores(
            employee_id=kpi.employee_id,
            employee_name=kpi.employee_name,
            team=employee_by_id[kpi.employee_id].team,
            role=employee_by_id[kpi.employee_id].role,
            productivity_score=kpi.productivity_score,
            productivity_reason=kpi.productivity_reason,
            compliance_score=kpi.compliance_score,
            compliance_reason=kpi.compliance_reason,
            quality_score=kpi.quality_score,
            quality_reason=kpi.quality_reason,
            data_confidence=kpi.data_confidence,
            confidence_threshold=kpi.confidence_threshold,
            confidence_reason=kpi.confidence_reason,
            overall_score=kpi.overall_score,
            result_status=kpi.result_status,
            performance_tier=kpi.performance_tier,
            supporting_record_ids=kpi.supporting_record_ids,
            evidence_links=sorted(
                {
                    project_links[record_id]
                    for record_id in kpi.supporting_record_ids
                    if record_id in project_links
                }
            ),
            validation_findings=[
                finding
                for finding in scoped_findings
                if finding.employee_id == kpi.employee_id
            ],
        )
        for kpi in kpi_results
    ]
    alerts = build_performance_alerts(
        performance_dataset,
        scoped_findings,
        result_employee_ids,
        included_record_ids,
    )
    limitations = _build_limitations(
        performance_dataset,
        analysis.mapping_proposals,
        import_issues,
        scoped_findings,
    )
    analysis_id = _cache_insight_context(employee_results)

    return AnalyzeUploadResponse(
        analysis_id=analysis_id,
        file_name=upload_catalog.file_name,
        file_type=upload_catalog.file_type,
        byte_size=upload_catalog.byte_size,
        results=employee_results,
        summary=_build_analysis_summary(kpi_results),
        dataset_overview=overview,
        applied_filters=AnalysisFilters(
            employee_id=employee_id,
            team=team,
            start_date=start_date or overview.date_start,
            end_date=end_date or overview.date_end,
        ),
        available_teams=available_teams,
        trends=calculate_weekly_kpi_trends(
            performance_dataset,
            start_date=start_date,
            end_date=end_date,
            employee_id=employee_id,
            team=team,
        ),
        alerts=alerts,
        import_issues=import_issues,
        validation_summary=summarize_validation(scoped_findings),
        global_validation_findings=[
            finding
            for finding in scoped_findings
            if finding.employee_id not in known_employee_ids
        ],
        selected_tables=analysis.selected_tables,
        limitations=limitations,
        model=get_settings().openai_model,
        total_tokens=usage.total_tokens,
        model_requests=usage.requests,
        mapping_cache_hit=mapping_cache_hit,
    )


def _build_analysis_summary(kpi_results: list[KpiResult]) -> AnalysisSummary:
    insufficient_ids = [
        result.employee_id
        for result in kpi_results
        if result.result_status == "Insufficient data"
    ]
    tier_counts: dict[str, int] = {}
    for result in kpi_results:
        if result.performance_tier is not None:
            tier_counts[result.performance_tier] = (
                tier_counts.get(result.performance_tier, 0) + 1
            )

    total_count = len(kpi_results)
    insufficient_count = len(insufficient_ids)
    scored_count = total_count - insufficient_count
    narrative = (
        f"Analyzed {total_count} employees. {scored_count} received an overall "
        f"performance result; {insufficient_count} were marked Insufficient data "
        "because their evidence confidence was below the configured threshold."
    )
    return AnalysisSummary(
        total_employee_count=total_count,
        scored_employee_count=scored_count,
        insufficient_data_count=insufficient_count,
        insufficient_data_employee_ids=insufficient_ids,
        performance_tier_counts=dict(sorted(tier_counts.items())),
        narrative=narrative,
    )


def _build_insight_context(
    employee_results: list[EmployeeKpiScores],
) -> dict[str, InsightEmployeeContext]:
    context: dict[str, InsightEmployeeContext] = {}
    for result in employee_results:
        grouped: dict[tuple[str, str, str], list[str]] = {}
        for finding in result.validation_findings:
            if not finding.record_ids:
                continue
            key = (finding.code, finding.message, finding.scoring_impact)
            grouped.setdefault(key, []).extend(finding.record_ids)
        if not grouped:
            continue
        allowed_record_ids = frozenset(
            record_id
            for record_ids in grouped.values()
            for record_id in record_ids
        )
        findings = [
            {
                "code": code,
                "message": message,
                "scoring_impact": scoring_impact,
                "occurrence_count": len(set(record_ids)),
                "record_ids": list(dict.fromkeys(record_ids))[:5],
            }
            for (code, message, scoring_impact), record_ids in grouped.items()
        ]
        context[result.employee_id] = InsightEmployeeContext(
            prompt_context={
                "employee_id": result.employee_id,
                "employee_name": result.employee_name,
                "result_status": result.result_status,
                "performance_tier": result.performance_tier,
                "findings": findings,
            },
            allowed_record_ids=allowed_record_ids,
        )
    return context


def _cache_insight_context(employee_results: list[EmployeeKpiScores]) -> str:
    _remove_expired_insight_contexts()
    analysis_id = token_urlsafe(24)
    _insight_context_cache[analysis_id] = CachedInsightContext(
        created_at=datetime.now(UTC),
        employees=_build_insight_context(employee_results),
    )
    while len(_insight_context_cache) > _INSIGHT_CONTEXT_CACHE_MAX_SIZE:
        _insight_context_cache.popitem(last=False)
    return analysis_id


def _get_insight_context(analysis_id: str) -> CachedInsightContext | None:
    _remove_expired_insight_contexts()
    context = _insight_context_cache.get(analysis_id)
    if context is not None:
        _insight_context_cache.move_to_end(analysis_id)
    return context


def _remove_expired_insight_contexts() -> None:
    cutoff = datetime.now(UTC) - _INSIGHT_CONTEXT_TTL
    expired_ids = [
        analysis_id
        for analysis_id, context in _insight_context_cache.items()
        if context.created_at < cutoff
    ]
    for analysis_id in expired_ids:
        del _insight_context_cache[analysis_id]


async def generate_employee_insight(
    analysis_id: str,
    employee_id: str,
) -> AIInsightResponse:
    """Generate validated guidance from a temporary deterministic analysis context."""
    cached = _get_insight_context(analysis_id)
    if cached is None:
        raise InsightContextExpiredError(
            "This analysis has expired. Run the file analysis again before requesting AI guidance."
        )
    employee_context = cached.employees.get(employee_id)
    if employee_context is None:
        raise InsightUnavailableError(
            "This employee has no validated findings available for AI guidance."
        )

    usage = RunUsage()
    try:
        insight = await _run_insight_agent(employee_context.prompt_context, usage)
    except AIUnavailableError:
        raise
    except (
        ModelHTTPError,
        UnexpectedModelBehavior,
        UsageLimitExceeded,
        UserError,
    ) as exc:
        raise AIError(f"The insight model call failed: {exc}") from exc

    if not _validate_ai_insight(insight, employee_id, employee_context.allowed_record_ids):
        raise AIError(
            "The generated insight was omitted because its employee or record citations did not validate."
        )
    return AIInsightResponse(
        insight=insight,
        model=get_settings().openai_model,
        total_tokens=usage.total_tokens,
        model_requests=usage.requests,
    )


async def _run_insight_agent(
    insight_context: dict[str, object],
    usage: RunUsage,
) -> EmployeeAIInsight:
    prompt = (
        "Write one concise evidence-backed explanation and at most two constructive next "
        "steps for this employee.\n\n"
        + json.dumps(insight_context, ensure_ascii=False, separators=(",", ":"))
    )
    result = await insights_agent.run(
        prompt,
        model=get_model(),
        model_settings=OpenAIResponsesModelSettings(
            openai_prompt_cache_key="employee-performance-insights-v1",
            openai_text_verbosity="low",
        ),
        usage=usage,
        usage_limits=UsageLimits(request_limit=2, total_tokens_limit=12_000),
    )
    return result.output


def _validate_ai_insight(
    insight: EmployeeAIInsight,
    employee_id: str,
    allowed_record_ids: frozenset[str],
) -> bool:
    statements = [insight.explanation, *insight.recommendations]
    return insight.employee_id == employee_id and all(
        set(statement.record_ids).issubset(allowed_record_ids)
        for statement in statements
    )


async def _run_mapping_agent(
    workbook_context: dict[str, object],
    usage: RunUsage,
) -> UploadAnalysis:
    prompt = (
        "Map the relevant source tables to the canonical employee-performance schema. "
        "The synopsis is bounded and may include irrelevant benchmark or documentation "
        "tables; ignore those.\n\n"
        + json.dumps(workbook_context, ensure_ascii=False, separators=(",", ":"))
    )
    result = await analysis_agent.run(
        prompt,
        model=get_model(),
        model_settings=_mapping_model_settings(),
        usage=usage,
        usage_limits=_mapping_usage_limits(),
    )
    return result.output


async def _repair_mappings(
    workbook_context: dict[str, object],
    analysis: UploadAnalysis,
    invalid_mappings: list[MappingValidation],
    usage: RunUsage,
) -> UploadAnalysis:
    prompt = (
        "Correct only the structurally invalid mappings and return the complete mapping "
        "output again. Preserve mappings that already validate.\n\n"
        "CURRENT_OUTPUT:\n"
        + analysis.model_dump_json()
        + "\n\nVALIDATION_ERRORS:\n"
        + json.dumps(
            [
                validation.model_dump(mode="json")
                for validation in invalid_mappings
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n\nWORKBOOK_SYNOPSIS:\n"
        + json.dumps(workbook_context, ensure_ascii=False, separators=(",", ":"))
    )
    result = await analysis_agent.run(
        prompt,
        model=get_model(),
        model_settings=_mapping_model_settings(),
        usage=usage,
        usage_limits=_mapping_usage_limits(),
    )
    return result.output


def _build_workbook_context(upload_catalog: UploadCatalog) -> dict[str, object]:
    analyses = catalog.inspect_tables(
        upload_catalog,
        [table.source_name for table in upload_catalog.tables],
    )
    return {
        "canonical_schema": catalog.canonical_mapping_contract(),
        "tables": [
            {
                "source_name": analysis.description.source_name,
                "row_count": analysis.description.row_count,
                "columns": [
                    column.model_dump(mode="json")
                    for column in analysis.description.columns
                ],
                "duplicate_row_count": analysis.profile.duplicate_row_count,
                "sample_rows": analysis.description.sample_rows[:2],
            }
            for analysis in analyses
        ],
    }


def _schema_fingerprint(
    upload_catalog: UploadCatalog,
) -> str:
    schema_only = {
        "file_type": upload_catalog.file_type,
        "tables": [
            {
                "source_name": table.source_name,
                "columns": table.columns,
                "column_types": {
                    column: sorted(
                        {
                            type(row.get(column)).__name__
                            for row in table.rows
                            if row.get(column) is not None
                        }
                    )
                    for column in table.columns
                },
            }
            for table in upload_catalog.tables
        ],
    }
    encoded = json.dumps(schema_only, sort_keys=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()


def _get_cached_analysis(schema_fingerprint: str) -> UploadAnalysis | None:
    analysis = _mapping_cache.get(schema_fingerprint)
    if analysis is None:
        return None
    _mapping_cache.move_to_end(schema_fingerprint)
    return analysis.model_copy(deep=True)


def _cache_analysis(
    schema_fingerprint: str,
    analysis: UploadAnalysis,
) -> None:
    _mapping_cache[schema_fingerprint] = analysis.model_copy(deep=True)
    _mapping_cache.move_to_end(schema_fingerprint)
    while len(_mapping_cache) > _MAPPING_CACHE_MAX_SIZE:
        _mapping_cache.popitem(last=False)


def _mapping_model_settings() -> OpenAIResponsesModelSettings:
    return OpenAIResponsesModelSettings(
        openai_prompt_cache_key="employee-performance-mapping-v1",
        openai_text_verbosity="low",
    )


def _mapping_usage_limits() -> UsageLimits:
    return UsageLimits(
        request_limit=3,
        total_tokens_limit=60_000,
    )


def _build_limitations(
    dataset: PerformanceDataset,
    mappings: list[MappingProposal],
    import_issues: list[ImportIssue],
    validation_findings: list[ValidationFinding],
) -> list[str]:
    limitations: list[str] = []
    uncertain_sources = sorted(
        proposal.source_name
        for proposal in mappings
        if proposal.confidence != "high"
    )
    if uncertain_sources:
        limitations.append(
            "Mapping confidence was below high for: " + ", ".join(uncertain_sources) + "."
        )
    if import_issues:
        limitations.append(
            f"{len(import_issues)} source rows or mappings could not be imported."
        )
    if dataset.attendance and "actual_end" not in dataset.mapped_fields.get(
        "attendance", set()
    ):
        limitations.append(
            "Attendance end-time validation was unavailable because actual_end was not mapped."
        )
    excluded_count = summarize_validation(validation_findings).excluded_record_count
    if excluded_count:
        limitations.append(
            f"{excluded_count} invalid or duplicate records were excluded from scoring."
        )
    return limitations
