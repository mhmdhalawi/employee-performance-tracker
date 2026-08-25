from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import UnexpectedModelBehavior, UserError
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.core.config import get_settings
from app.core.errors import AIError, AIUnavailableError
from app.schemas.uploads import (
    DistinctValues,
    MappingProposal,
    MappingValidation,
    RowPage,
    TableDescription,
    TableInspection,
    TableProfile,
    UploadCatalog,
)
from app.services import catalog

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


agent = Agent[UploadCatalog | None, str](
    name="employee_performance_agent",
    instructions=INSTRUCTIONS,
    deps_type=UploadCatalog | None,
)


@agent.tool
def list_tables(ctx: RunContext[UploadCatalog | None]) -> list[TableInspection] | str:
    """List available tables with their headers, dimensions, and row counts. Use this first."""
    if ctx.deps is None:
        return _missing_catalog_message()
    return catalog.list_tables(ctx.deps)


@agent.tool
def describe_table(
    ctx: RunContext[UploadCatalog | None],
    table_name: str,
) -> TableDescription | str:
    """Describe one table's inferred column types, missing values, unique values, and five sample rows."""
    if ctx.deps is None:
        return _missing_catalog_message()
    return catalog.describe_table(ctx.deps, table_name)


@agent.tool
def get_rows(
    ctx: RunContext[UploadCatalog | None],
    table_name: str,
    columns: list[str] | None = None,
    filters: dict[str, str] | None = None,
    sort_by: str | None = None,
    descending: bool = False,
    limit: Annotated[int, Field(ge=1, le=100)] = 20,
) -> RowPage | str:
    """Return up to 100 selected source rows, with optional exact-match filters and sorting."""
    if ctx.deps is None:
        return _missing_catalog_message()
    return catalog.get_rows(
        ctx.deps,
        table_name,
        columns,
        filters,
        sort_by,
        descending,
        limit,
    )


@agent.tool
def profile_data(
    ctx: RunContext[UploadCatalog | None],
    table_name: str,
) -> TableProfile | str:
    """Detect blank columns, duplicate rows, and likely ID, date, and numeric columns."""
    if ctx.deps is None:
        return _missing_catalog_message()
    return catalog.profile_data(ctx.deps, table_name)


@agent.tool
def search_rows(
    ctx: RunContext[UploadCatalog | None],
    query: str,
    table_name: str | None = None,
    limit: Annotated[int, Field(ge=1, le=100)] = 20,
) -> list[RowPage] | str:
    """Find a text fragment across a chosen table or every table, returning bounded source rows."""
    if ctx.deps is None:
        return _missing_catalog_message()
    return catalog.search_rows(ctx.deps, query, table_name, limit)


@agent.tool
def get_distinct_values(
    ctx: RunContext[UploadCatalog | None],
    table_name: str,
    column: str,
    limit: Annotated[int, Field(ge=1, le=50)] = 20,
) -> DistinctValues | str:
    """Return up to 50 non-empty distinct values to understand a source column's categories."""
    if ctx.deps is None:
        return _missing_catalog_message()
    return catalog.get_distinct_values(ctx.deps, table_name, column, limit)


@agent.tool
def propose_mapping(
    ctx: RunContext[UploadCatalog | None],
    source_name: str,
    canonical_entity: str,
    field_mappings: dict[str, str],
    confidence: Literal["low", "medium", "high"],
    rationale: str,
) -> MappingProposal | str:
    """Record a tentative mapping from a source table to a canonical performance entity."""
    if ctx.deps is None:
        return _missing_catalog_message()
    return catalog.propose_mapping(
        ctx.deps,
        source_name,
        canonical_entity,
        field_mappings,
        confidence,
        rationale,
    )


@agent.tool
def validate_mapping(
    ctx: RunContext[UploadCatalog | None],
    source_name: str,
    canonical_entity: str,
    field_mappings: dict[str, str],
) -> MappingValidation | str:
    """Validate mapped columns, required fields, and duplicate source-column use before scoring."""
    if ctx.deps is None:
        return _missing_catalog_message()
    return catalog.validate_mapping(ctx.deps, source_name, canonical_entity, field_mappings)


@lru_cache
def get_model() -> OpenAIChatModel:
    """Return the configured model or raise when no API key is available."""
    settings = get_settings()
    if not settings.openai_api_key:
        raise AIUnavailableError("OPENAI_API_KEY is not set, so the agent cannot run.")

    return OpenAIChatModel(
        settings.openai_model,
        provider=OpenAIProvider(api_key=settings.openai_api_key),
    )


async def ask(
    prompt: str,
    catalog: UploadCatalog | None = None,
) -> tuple[str, int]:
    """Run the agent with an optional request-scoped upload catalog."""
    try:
        result = await agent.run(prompt, model=get_model(), deps=catalog)
    except (UnexpectedModelBehavior, UserError) as exc:
        raise AIError(f"The model call failed: {exc}") from exc

    return result.output, result.usage.total_tokens


def _missing_catalog_message() -> str:
    return "No uploaded CSV or Excel catalog is available for this request."
