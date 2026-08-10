from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import RowIssue

KpiFamily = Literal["productivity", "quality", "compliance"]
MetricDirection = Literal["higher_better", "lower_better"]


class KpiComponent(BaseModel):
    """One metric's contribution to a family score."""

    metric: str
    label: str
    source_field: str | None = Field(
        default=None, description="Header in the uploaded file this value came from."
    )
    available: bool = True
    raw_value: float | None = None
    unit: str | None = None
    target: float
    direction: MetricDirection
    normalized_score: float | None = Field(
        default=None, description="0-100 score for this metric alone."
    )
    weight: float = Field(description="Declared weight from the role profile.")
    effective_weight: float = Field(
        default=0.0, description="Weight after renormalizing over available metrics."
    )
    contribution: float = Field(
        default=0.0, description="normalized_score * effective_weight."
    )
    note: str | None = None


class KpiFamilyScore(BaseModel):
    family: KpiFamily
    score: float | None = Field(
        default=None, description="0-100, or None when no metric was available."
    )
    reason: str | None = Field(
        default=None, description="Why the score is None, when it is."
    )
    components: list[KpiComponent] = Field(default_factory=list)
    missing_metrics: list[str] = Field(default_factory=list)


class EmployeeKpiResult(BaseModel):
    employee_id: str
    employee_name: str | None = None
    profile: str
    period: str | None = None
    overall_score: float | None = None
    families: dict[KpiFamily, KpiFamilyScore]
    source_row: int


class BatchResult(BaseModel):
    """Everything produced by one ingestion, cached in the batch store."""

    batch_id: str
    created_at: datetime
    filename: str
    profile: str
    row_count: int = Field(description="Data rows read from the file.")
    scored_count: int = Field(description="Rows that produced a KPI result.")
    employees: list[EmployeeKpiResult] = Field(default_factory=list)
    issues: list[RowIssue] = Field(default_factory=list)
