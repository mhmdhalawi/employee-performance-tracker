from typing import Literal

from pydantic import BaseModel, Field

MappingMode = Literal["aliases", "hybrid", "ai"]
MappingSource = Literal["alias", "ai"]


class ColumnPreview(BaseModel):
    column: str
    non_empty: int
    numeric_ratio: float = Field(
        ge=0, le=1, description="Share of non-empty cells that parse as numbers."
    )
    sample_values: list[str] = Field(default_factory=list)
    numeric_min: float | None = None
    numeric_max: float | None = None
    numeric_mean: float | None = None


class MappingSuggestion(BaseModel):
    source_column: str
    metric: str = Field(description="Canonical metric name; must already exist in the profile.")
    confidence: float = Field(ge=0, le=1)
    reasoning: str


class AgentMappingProposal(BaseModel):
    profile: str
    profile_reasoning: str
    mappings: list[MappingSuggestion] = Field(default_factory=list)
    identifier_column: str | None = None
    name_column: str | None = None
    period_column: str | None = None
    unmapped_columns: list[str] = Field(default_factory=list)
    notes: str | None = None


class ResolvedMapping(BaseModel):
    column: str
    field: str = Field(description="Canonical metric name, or employee_id/employee_name/period.")
    source: MappingSource
    confidence: float | None = Field(
        default=None, description="Only present for AI-proposed mappings."
    )
    reasoning: str | None = None
