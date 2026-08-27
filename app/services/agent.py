from functools import lru_cache
from typing import Annotated

from pydantic import Field
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.exceptions import (
    ModelHTTPError,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
    UserError,
)
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

from app.core.config import get_settings
from app.core.errors import AIError, AIUnavailableError
from app.schemas.performance import (
    EmployeeKpiScores,
    PerformanceDataset,
    ValidationFinding,
)
from app.schemas.uploads import (
    AnalyzeUploadResponse,
    DistinctValues,
    ImportIssue,
    MappingProposal,
    MappingValidation,
    RowPage,
    TableAnalysis,
    TableInspection,
    UploadAnalysis,
    UploadCatalog,
)
from app.services import catalog
from app.services.datasets import build_performance_dataset
from app.services.imports import parse_upload
from app.services.performance import (
    calculate_kpis,
    summarize_validation,
    validate_dataset,
)

INSTRUCTIONS = """
You are the analysis agent for an Employee Performance Tracker.

First understand the uploaded file before deciding what, if anything, should be calculated.
Call `list_tables` exactly once. Then call `inspect_tables` once with all tables that may be
relevant; it returns bounded descriptions, profiles, and samples together. Use
`get_distinct_values`, `get_rows`, or `search_rows` only when a specific column remains
ambiguous after bulk inspection. Never request the entire file.

Do not infer meaning from a sheet name alone. Draft all mapping proposals, then call
`validate_mappings` once with the complete list. Correct any structurally invalid mappings
before returning them. Map optional fields that support validation, including attendance
`actual_end`, whenever a matching source column exists. If a semantic mapping is uncertain,
return a lower confidence instead of making additional broad inspections. Do not validate
source records or calculate scores; Python does that after you return the mappings.

The tools calculate and inspect; you interpret and explain. Do not calculate, count, average,
score, or state a numeric result unless it was returned by a tool. Do not invent a metric,
mapping, source record, evidence link, or missing-data value. If no upload catalog is
available, explain that the request needs an uploaded CSV or Excel file.
"""


analysis_agent = Agent[UploadCatalog, UploadAnalysis](
    name="employee_performance_agent",
    instructions=INSTRUCTIONS,
    deps_type=UploadCatalog,
    output_type=UploadAnalysis,
)


@analysis_agent.tool
def list_tables(ctx: RunContext[UploadCatalog]) -> list[TableInspection]:
    """List available tables with their headers, dimensions, and row counts. Use this first."""
    return catalog.list_tables(ctx.deps)


@analysis_agent.tool(retries=2)
def inspect_tables(
    ctx: RunContext[UploadCatalog],
    table_names: Annotated[list[str], Field(min_length=1, max_length=20)],
) -> list[TableAnalysis]:
    """Describe and profile up to 20 selected tables with three sample rows each."""
    try:
        return catalog.inspect_tables(ctx.deps, table_names)
    except ValueError as exc:
        raise ModelRetry(str(exc)) from exc


@analysis_agent.tool(retries=2)
def get_rows(
    ctx: RunContext[UploadCatalog],
    table_name: str,
    columns: list[str] | None = None,
    filters: dict[str, str] | None = None,
    sort_by: str | None = None,
    descending: bool = False,
    limit: Annotated[int, Field(ge=1, le=100)] = 20,
) -> RowPage:
    """Return up to 100 selected source rows, with optional exact-match filters and sorting."""
    try:
        return catalog.get_rows(
            ctx.deps,
            table_name,
            columns,
            filters,
            sort_by,
            descending,
            limit,
        )
    except ValueError as exc:
        raise ModelRetry(str(exc)) from exc


@analysis_agent.tool(retries=2)
def search_rows(
    ctx: RunContext[UploadCatalog],
    query: str,
    table_name: str | None = None,
    limit: Annotated[int, Field(ge=1, le=100)] = 20,
) -> list[RowPage]:
    """Find a text fragment across a chosen table or every table, returning bounded source rows."""
    try:
        return catalog.search_rows(ctx.deps, query, table_name, limit)
    except ValueError as exc:
        raise ModelRetry(str(exc)) from exc


@analysis_agent.tool(retries=2)
def get_distinct_values(
    ctx: RunContext[UploadCatalog],
    table_name: str,
    column: str,
    limit: Annotated[int, Field(ge=1, le=50)] = 20,
) -> DistinctValues:
    """Return up to 50 non-empty distinct values to understand a source column's categories."""
    try:
        return catalog.get_distinct_values(ctx.deps, table_name, column, limit)
    except ValueError as exc:
        raise ModelRetry(str(exc)) from exc


@analysis_agent.tool(retries=2)
def validate_mappings(
    ctx: RunContext[UploadCatalog],
    mappings: Annotated[list[MappingProposal], Field(min_length=1, max_length=20)],
) -> list[MappingValidation]:
    """Validate all proposed mappings together before returning the final analysis."""
    try:
        return catalog.validate_mappings(ctx.deps, mappings)
    except ValueError as exc:
        raise ModelRetry(str(exc)) from exc


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
) -> AnalyzeUploadResponse:
    """Parse an upload and let the agent select and map relevant source tables."""
    upload_catalog = parse_upload(file_name, contents, maximum_bytes)
    try:
        result = await analysis_agent.run(
            "Inspect this upload and identify the tables and fields that can support employee performance calculations. Propose and validate the mappings Python needs to calculate the three KPI scores. Do not calculate scores yourself.",
            model=get_model(),
            deps=upload_catalog,
            usage_limits=UsageLimits(
                request_limit=35,
                total_tokens_limit=60_000,
                count_tokens_before_request=True,
            ),
        )
    except (
        ModelHTTPError,
        UnexpectedModelBehavior,
        UsageLimitExceeded,
        UserError,
    ) as exc:
        raise AIError(f"The model call failed: {exc}") from exc

    performance_dataset, mapping_issues = build_performance_dataset(
        upload_catalog,
        result.output.mapping_proposals,
    )
    validation_findings = validate_dataset(performance_dataset)
    kpi_results = calculate_kpis(
        performance_dataset,
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

    return AnalyzeUploadResponse(
        file_name=upload_catalog.file_name,
        file_type=upload_catalog.file_type,
        byte_size=upload_catalog.byte_size,
        results=[
            EmployeeKpiScores(
                employee_id=kpi.employee_id,
                employee_name=kpi.employee_name,
                productivity_score=kpi.productivity_score,
                productivity_reason=kpi.productivity_reason,
                compliance_score=kpi.compliance_score,
                compliance_reason=kpi.compliance_reason,
                quality_score=kpi.quality_score,
                quality_reason=kpi.quality_reason,
                validation_findings=[
                    finding
                    for finding in validation_findings
                    if finding.employee_id == kpi.employee_id
                ],
            )
            for kpi in kpi_results
        ],
        import_issues=import_issues,
        validation_summary=summarize_validation(validation_findings),
        global_validation_findings=[
            finding
            for finding in validation_findings
            if finding.employee_id not in result_employee_ids
        ],
        selected_tables=[table.source_name for table in result.output.selected_tables],
        limitations=_build_limitations(
            performance_dataset,
            result.output.mapping_proposals,
            import_issues,
            validation_findings,
        ),
        model=get_settings().openai_model,
        total_tokens=result.usage.total_tokens,
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
