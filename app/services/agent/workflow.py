from dataclasses import dataclass
from datetime import date
from time import perf_counter

from pydantic_ai.exceptions import (
    ModelHTTPError,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
    UserError,
)
from pydantic_ai.usage import RunUsage

from app.core.config import get_settings
from app.core.errors import AIError, InvalidAnalysisFilterError
from app.schemas.performance import PerformanceEvidenceDataset, ValidationFinding
from app.schemas.tables import AnalyzeTablesRequest
from app.schemas.uploads import (
    AnalysisResponse,
    AnalyzeTablesPreviewResponse,
    CalculationPlan,
    DataCatalog,
    ImportIssue,
)
from app.services import catalog
from app.services.aggregation import canonicalize_batch
from app.services.agent.cache import (
    _cache_analysis,
    _get_cached_analysis,
    catalog_schema_fingerprint,
)
from app.services.agent.context import _build_workbook_context
from app.services.agent.planning import (
    _expand_agent_plan,
    _repair_mappings,
    _run_mapping_agent,
)
from app.services.agent.response import build_analysis_response
from app.services.datasets import build_performance_dataset
from app.services.tables import catalog_from_tables

@dataclass(frozen=True, slots=True)
class AnalysisArtifacts:
    schema_fingerprint: str
    calculation_plan: CalculationPlan
    performance_dataset: PerformanceEvidenceDataset
    response: AnalysisResponse
    input_tokens: int
    output_tokens: int
    llm_duration_ms: float

async def analyze_tables_artifacts(
    request: AnalyzeTablesRequest,
    employee_id: str | None = None,
    team: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    calculation_plan: CalculationPlan | None = None,
    available_foundation_calculators: set[str] | None = None,
) -> AnalysisArtifacts:
    """Return validated ingestion artifacts and the deterministic batch analysis."""
    return await analyze_catalog_artifacts(
        catalog_from_tables(request),
        import_issues=[],
        employee_id=employee_id,
        team=team,
        start_date=start_date,
        end_date=end_date,
        calculation_plan=calculation_plan,
        canonicalize_batch_records=True,
        available_foundation_calculators=available_foundation_calculators,
    )


async def preview_tables_analysis(
    request: AnalyzeTablesRequest,
) -> AnalyzeTablesPreviewResponse:
    """Analyze one complete JSON dataset without reading or writing persistence."""
    artifacts = await analyze_tables_artifacts(request)
    return AnalyzeTablesPreviewResponse(
        **artifacts.response.model_dump(),
        input_tokens=artifacts.input_tokens,
        output_tokens=artifacts.output_tokens,
        llm_duration_ms=artifacts.llm_duration_ms,
    )


async def analyze_catalog_artifacts(
    source_catalog: DataCatalog,
    import_issues: list[ImportIssue],
    employee_id: str | None = None,
    team: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    calculation_plan: CalculationPlan | None = None,
    canonicalize_batch_records: bool = False,
    available_foundation_calculators: set[str] | None = None,
) -> AnalysisArtifacts:
    """Resolve a plan, bind canonical evidence, and construct a deterministic response."""
    if start_date and end_date and start_date > end_date:
        raise InvalidAnalysisFilterError("start_date must be on or before end_date.")
    workbook_context = _build_workbook_context(source_catalog)
    schema_fingerprint = catalog_schema_fingerprint(source_catalog)
    analysis = (
        calculation_plan.model_copy(deep=True)
        if calculation_plan is not None
        else _get_cached_analysis(schema_fingerprint)
    )
    if analysis is not None and any(
        not validation.valid
        for validation in catalog.validate_classifications(
            source_catalog,
            analysis.table_classifications,
            available_foundation_calculators=available_foundation_calculators,
        )
    ):
        analysis = None
    mapping_cache_hit = analysis is not None
    usage = RunUsage()
    llm_duration_seconds = 0.0

    if analysis is None:
        try:
            llm_started = perf_counter()
            agent_plan = await _run_mapping_agent(
                workbook_context,
                usage,
            )
            llm_duration_seconds += perf_counter() - llm_started
            analysis = _expand_agent_plan(agent_plan)
            invalid_classifications = [
                validation
                for validation in catalog.validate_classifications(
                    source_catalog,
                    analysis.table_classifications,
                    available_foundation_calculators=available_foundation_calculators,
                )
                if not validation.valid
            ]
            if invalid_classifications:
                llm_started = perf_counter()
                agent_plan = await _repair_mappings(
                    source_catalog,
                    workbook_context,
                    agent_plan,
                    invalid_classifications,
                    usage,
                )
                llm_duration_seconds += perf_counter() - llm_started
                analysis = _expand_agent_plan(agent_plan)
        except (
            ModelHTTPError,
            UnexpectedModelBehavior,
            UsageLimitExceeded,
            UserError,
        ) as exc:
            raise AIError(f"The model call failed: {exc}") from exc

        final_validations = catalog.validate_classifications(
            source_catalog,
            analysis.table_classifications,
            available_foundation_calculators=available_foundation_calculators,
        )
        invalid_final_validations = [
            validation for validation in final_validations if not validation.valid
        ]
        if invalid_final_validations:
            raise AIError(
                "The model calculation plan did not pass deterministic validation."
            )
        _cache_analysis(schema_fingerprint, analysis)

    performance_dataset, mapping_issues = build_performance_dataset(
        source_catalog,
        analysis.table_classifications,
    )
    batch_findings: list[ValidationFinding] = []
    if canonicalize_batch_records:
        performance_dataset, batch_findings = canonicalize_batch(performance_dataset)
    all_import_issues = [*import_issues, *mapping_issues]
    response = build_analysis_response(
        performance_dataset,
        analysis,
        import_issues=all_import_issues,
        employee_id=employee_id,
        team=team,
        start_date=start_date,
        end_date=end_date,
        additional_validation_findings=batch_findings,
        model=get_settings().openai_model,
        total_tokens=usage.total_tokens,
        model_requests=usage.requests,
        mapping_cache_hit=mapping_cache_hit,
    )
    return AnalysisArtifacts(
        schema_fingerprint=schema_fingerprint,
        calculation_plan=analysis,
        performance_dataset=performance_dataset,
        response=response,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        llm_duration_ms=round(llm_duration_seconds * 1000, 2),
    )

