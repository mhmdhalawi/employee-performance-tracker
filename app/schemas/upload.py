from pydantic import BaseModel, Field

from app.schemas.common import RowIssue
from app.schemas.kpi import EmployeeKpiResult
from app.schemas.mapping import MappingMode, ResolvedMapping


class UploadResponse(BaseModel):
    batch_id: str
    filename: str
    profile: str = Field(description="Role profile used, detected or explicitly requested.")
    profile_detected: bool = Field(
        description="True when the profile was inferred from the file's columns."
    )
    mapping_mode: MappingMode = Field(
        description="Mapping strategy actually used; 'hybrid'/'ai' fall back to 'aliases' "
        "when no model is configured."
    )
    row_count: int
    scored_count: int
    employees: list[EmployeeKpiResult]
    resolved_mappings: list[ResolvedMapping] = Field(
        default_factory=list,
        description="Which column fed which field, and whether an alias or the AI decided it.",
    )
    issues: list[RowIssue] = Field(
        default_factory=list,
        description="Row-level problems. A non-empty list does not mean the upload failed.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Mapping-level concerns, e.g. low-confidence AI mappings worth reviewing.",
    )
    unmapped_columns: list[str] = Field(
        default_factory=list,
        description="Headers nothing claimed. Ignored during scoring.",
    )
    ai_notes: str | None = Field(
        default=None, description="Free-text remarks from the mapping agent, if it ran."
    )

    @classmethod
    def from_outcome(cls, outcome) -> "UploadResponse":
        batch = outcome.batch
        return cls(
            batch_id=batch.batch_id,
            filename=batch.filename,
            profile=batch.profile,
            profile_detected=outcome.profile_detected,
            mapping_mode=outcome.mapping_mode_used,
            row_count=batch.row_count,
            scored_count=batch.scored_count,
            employees=batch.employees,
            resolved_mappings=outcome.resolved_mappings,
            issues=batch.issues,
            warnings=outcome.warnings,
            unmapped_columns=outcome.unmapped_columns,
            ai_notes=outcome.ai_notes,
        )


class BatchSummary(BaseModel):
    """Listing entry — no per-employee detail."""

    batch_id: str
    filename: str
    profile: str
    created_at: str
    row_count: int
    scored_count: int
    issue_count: int


class MetricInfo(BaseModel):
    metric: str
    label: str
    family: str
    direction: str
    target: float
    weight: float
    unit: str | None = None
    accepted_columns: list[str]


class ProfileInfo(BaseModel):
    """Told to the dashboard so it can show expected columns before upload."""

    key: str
    label: str
    description: str
    metrics: list[MetricInfo]
