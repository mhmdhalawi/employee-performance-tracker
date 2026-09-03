from datetime import date, datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from app.schemas.performance import KpiTrendPoint


class EmployeeReportRequest(BaseModel):
    employee_id: str = Field(min_length=1, max_length=200)
    period_weeks: Literal[4, 8, 12] | None = None
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_period(self) -> Self:
        if self.period_weeks is not None and (
            self.start_date is not None or self.end_date is not None
        ):
            raise ValueError(
                "period_weeks cannot be combined with start_date or end_date."
            )
        if (self.start_date is None) != (self.end_date is None):
            raise ValueError("start_date and end_date must be provided together.")
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise ValueError("start_date must be on or before end_date.")
        return self


class ReportPeriod(BaseModel):
    start_date: date
    end_date: date
    prior_start_date: date | None = None
    prior_end_date: date | None = None


class ReportKpiSection(BaseModel):
    name: Literal["Productivity", "Compliance", "Quality"]
    score: float
    weight: float
    explanation: str


class ReportFinding(BaseModel):
    code: str
    severity: Literal["error", "warning", "info"]
    scoring_impact: Literal[
        "blocks_score",
        "excluded_from_scoring",
        "lowers_confidence",
        "affects_score",
        "none",
    ]
    message: str
    occurrence_count: int = Field(ge=1)
    record_ids: list[str]
    evidence_links: list[str]


class EmployeeReportData(BaseModel):
    employee_id: str
    employee_name: str | None
    team: str | None
    role: str | None
    period: ReportPeriod
    generated_at: datetime
    overall_score: float | None
    result_status: str
    performance_tier: str | None
    data_confidence: float
    confidence_threshold: float
    confidence_explanation: str
    kpis: list[ReportKpiSection] = Field(min_length=3, max_length=3)
    trends: list[KpiTrendPoint]
    prior_overall_score: float | None = None
    overall_score_change: float | None = None
    findings: list[ReportFinding]
    supporting_record_ids: list[str]
    metric_definitions: list[str]
    manager_review_notice: str


class EmployeeReportPreviewResponse(BaseModel):
    report: EmployeeReportData
    pdf_generated_by: Literal["browser"] = "browser"
