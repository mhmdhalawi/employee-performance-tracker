from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior, UserError
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.core.config import get_settings
from app.core.errors import AIError, AIUnavailableError
from app.schemas.performance import EmployeeKpiScores
from app.schemas.uploads import (
    AnalyzeUploadResponse,
    DistinctValues,
    ImportIssue,
    MappingProposal,
    MappingValidation,
    RowPage,
    TableDescription,
    TableInspection,
    TableProfile,
    UploadAnalysis,
    UploadCatalog,
)
from app.services import catalog
from app.services.datasets import build_performance_dataset
from app.services.imports import parse_upload
from app.services.performance import calculate_kpis

INSTRUCTIONS = """
You are the analysis agent for an Employee Performance Tracker.

First understand the uploaded file before deciding what, if anything, should be calculated.
Use `list_tables` first. Then use `describe_table`, `profile_data`, and
`get_distinct_values` to understand relevant tables and columns. Use `get_rows` or
`search_rows` only for small, relevant evidence samples. Never request the entire file.

Do not infer meaning from a sheet name alone. You may propose a mapping between source
columns and canonical performance concepts with `propose_mapping`, but must call
`validate_mapping` before treating it as usable. If the mapping is uncertain, say so.

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
def describe_table(
    ctx: RunContext[UploadCatalog],
    table_name: str,
) -> TableDescription:
    """Describe one table's inferred column types, missing values, unique values, and five sample rows."""
    try:
        return catalog.describe_table(ctx.deps, table_name)
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
def profile_data(
    ctx: RunContext[UploadCatalog],
    table_name: str,
) -> TableProfile:
    """Detect blank columns, duplicate rows, and likely ID, date, and numeric columns."""
    try:
        return catalog.profile_data(ctx.deps, table_name)
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
def propose_mapping(
    ctx: RunContext[UploadCatalog],
    source_name: str,
    canonical_entity: str,
    field_mappings: dict[str, str],
    confidence: Literal["low", "medium", "high"],
    rationale: str,
) -> MappingProposal:
    """Record a tentative mapping from a source table to a canonical performance entity."""
    try:
        return catalog.propose_mapping(
            ctx.deps,
            source_name,
            canonical_entity,
            field_mappings,
            confidence,
            rationale,
        )
    except ValueError as exc:
        raise ModelRetry(str(exc)) from exc


@analysis_agent.tool(retries=2)
def validate_mapping(
    ctx: RunContext[UploadCatalog],
    source_name: str,
    canonical_entity: str,
    field_mappings: dict[str, str],
) -> MappingValidation:
    """Validate mapped columns, required fields, and duplicate source-column use before scoring."""
    try:
        return catalog.validate_mapping(
            ctx.deps,
            source_name,
            canonical_entity,
            field_mappings,
        )
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
        )
    except (ModelHTTPError, UnexpectedModelBehavior, UserError) as exc:
        raise AIError(f"The model call failed: {exc}") from exc

    performance_dataset, mapping_issues = build_performance_dataset(
        upload_catalog,
        result.output.mapping_proposals,
    )
    kpi_results = calculate_kpis(performance_dataset)
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
            )
            for kpi in kpi_results
        ],
        import_issues=import_issues,
        selected_tables=[table.source_name for table in result.output.selected_tables],
        limitations=[
            limitation
            for limitation in result.output.limitations
            if not limitation.casefold().startswith("no kpi scores")
        ],
        model=get_settings().openai_model,
        total_tokens=result.usage.total_tokens,
    )
