from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class Employee(BaseModel):
    employee_id: str = Field(min_length=1)
    employee_name: str | None = None
    team: str | None = None
    role: str | None = None


class KpiTarget(BaseModel):
    employee_id: str = Field(min_length=1)
    target_projects_90d: float = Field(gt=0)
    target_avg_hours: float = Field(gt=0)
    minimum_confidence: float = Field(default=0.70, ge=0, le=1)


class Project(BaseModel):
    project_id: str = Field(min_length=1)
    employee_id: str = Field(min_length=1)
    assigned_date: date
    due_date: date
    completed_date: date | None = None
    project_status: str
    actual_hours: float | None = Field(default=None, gt=0)
    evidence_status: str
    evidence_link: str | None = None


class AttendanceRecord(BaseModel):
    attendance_id: str = Field(min_length=1)
    employee_id: str = Field(min_length=1)
    work_date: date
    arrival_status: str
    record_status: str
    actual_end: str | None = None
    confidence_score: float = Field(ge=0, le=1)


class Report(BaseModel):
    report_id: str = Field(min_length=1)
    employee_id: str = Field(min_length=1)
    due_date: date
    submitted_date: date | None = None
    submission_status: str
    completeness_pct: float = Field(ge=0, le=1)
    evidence_status: str


class LeaveRequest(BaseModel):
    leave_id: str = Field(min_length=1)
    employee_id: str = Field(min_length=1)
    leave_type: str
    start_date: date
    end_date: date
    request_status: str
    documentation_complete: bool


class QualityReview(BaseModel):
    review_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    employee_id: str = Field(min_length=1)
    review_date: date
    accuracy_pct: float = Field(ge=0, le=1)
    first_pass_approved: bool
    rework_hours: float = Field(ge=0)
    evidence_status: str


class PerformanceDataset(BaseModel):
    employees: list[Employee]
    kpi_targets: list[KpiTarget]
    projects: list[Project]
    attendance: list[AttendanceRecord]
    reports: list[Report]
    leave_requests: list[LeaveRequest]
    quality_reviews: list[QualityReview]
    mapped_fields: dict[str, set[str]] = Field(default_factory=dict)


class ValidationFinding(BaseModel):
    code: str
    severity: Literal["error", "warning", "info"]
    message: str
    record_ids: list[str]
    employee_id: str | None = None
    source_type: str | None = None
    scoring_impact: Literal[
        "blocks_score",
        "excluded_from_scoring",
        "lowers_confidence",
        "affects_score",
        "none",
    ] = "none"


class ValidationSummary(BaseModel):
    total_findings: int
    error_count: int
    warning_count: int
    info_count: int
    excluded_record_count: int
    affected_employee_count: int


class DatasetOverview(BaseModel):
    employee_count: int
    date_start: date | None
    date_end: date | None
    record_counts: dict[str, int]
    teams: list[str]


class KpiResult(BaseModel):
    employee_id: str
    employee_name: str | None
    productivity_score: float
    productivity_reason: str
    compliance_score: float
    compliance_reason: str
    quality_score: float
    quality_reason: str
    data_confidence: float
    confidence_threshold: float
    confidence_reason: str
    overall_score: float | None
    result_status: str
    performance_tier: str | None
    supporting_record_ids: list[str]


class EmployeeKpiScores(BaseModel):
    employee_id: str
    employee_name: str | None
    productivity_score: float
    productivity_reason: str
    compliance_score: float
    compliance_reason: str
    quality_score: float
    quality_reason: str
    data_confidence: float
    confidence_threshold: float
    confidence_reason: str
    overall_score: float | None
    result_status: str
    performance_tier: str | None
    supporting_record_ids: list[str]
    validation_findings: list[ValidationFinding] = Field(default_factory=list)


class EvidenceResult(BaseModel):
    employee_id: str
    record_ids: list[str]
    evidence_links: list[str]
    findings: list[ValidationFinding]


class KpiTrendResult(BaseModel):
    employee_id: str
    employee_name: str
    baseline_overall_score: float | None
    current_overall_score: float | None
    overall_score_change: float | None
    baseline_status: str
    current_status: str
