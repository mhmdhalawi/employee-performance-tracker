from typing import Any, Literal

from pydantic import BaseModel, Field

IssueSeverity = Literal["warning", "error"]


class RowIssue(BaseModel):
    """A per-row data problem. Reported, never silently fixed."""

    row: int = Field(description="1-based row number in the uploaded file.")
    column: str | None = None
    severity: IssueSeverity = "warning"
    message: str


class NormalizedRecord(BaseModel):
    """One employee's metrics for one period, in canonical form.

    Every supported input format is reduced to this shape by
    ``services.file_processor``. Downstream code only ever sees canonical
    metric names, never raw spreadsheet headers.
    """

    employee_id: str
    employee_name: str | None = None
    profile: str = Field(description="Role profile key, e.g. 'support' or 'developer'.")
    period: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    source_row: int
    raw: dict[str, Any] = Field(
        default_factory=dict,
        description="Original row, kept so any score can be traced to source data.",
    )


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail
