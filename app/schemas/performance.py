from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field


class Employee(BaseModel):
    employee_id: str = Field(min_length=1)
    employee_name: str | None = None
    team: str | None = None
    role: str | None = None
    source_version: int | None = Field(default=None, ge=0)
    source_updated_at: datetime | None = None


class PerformanceTarget(BaseModel):
    employee_id: str = Field(min_length=1)
    target_outputs_90d: float = Field(gt=0)
    target_avg_effort_hours: float = Field(gt=0)
    minimum_confidence: float = Field(default=0.70, ge=0, le=1)
    source_version: int | None = Field(default=None, ge=0)
    source_updated_at: datetime | None = None


class WorkOutputEvidence(BaseModel):
    record_id: str = Field(min_length=1)
    employee_id: str = Field(min_length=1)
    assigned_date: date
    due_date: date
    completed_date: date | None = None
    completion_status: str
    actual_effort_hours: float | None = Field(default=None, gt=0)
    verification_status: str
    evidence_link: str | None = None
    source_version: int | None = Field(default=None, ge=0)
    source_updated_at: datetime | None = None


class AttendanceComplianceEvidence(BaseModel):
    record_id: str = Field(min_length=1)
    employee_id: str = Field(min_length=1)
    occurred_on: date
    outcome: str
    record_status: str
    scheduled_start: time | None = None
    actual_start: time | None = None
    lunch_out: time | None = None
    lunch_in: time | None = None
    scheduled_end: time | None = None
    actual_end: time | None = None
    confidence_score: float = Field(ge=0, le=1)
    source_version: int | None = Field(default=None, ge=0)
    source_updated_at: datetime | None = None


class SubmissionComplianceEvidence(BaseModel):
    record_id: str = Field(min_length=1)
    employee_id: str = Field(min_length=1)
    due_date: date
    submitted_date: date | None = None
    outcome: str
    completeness_ratio: float = Field(ge=0, le=1)
    verification_status: str
    source_version: int | None = Field(default=None, ge=0)
    source_updated_at: datetime | None = None


class LeaveComplianceEvidence(BaseModel):
    record_id: str = Field(min_length=1)
    employee_id: str = Field(min_length=1)
    category: str
    start_date: date
    end_date: date
    outcome: str
    documentation_complete: bool
    source_version: int | None = Field(default=None, ge=0)
    source_updated_at: datetime | None = None


class QualityEvidence(BaseModel):
    record_id: str = Field(min_length=1)
    related_output_id: str = Field(min_length=1)
    employee_id: str = Field(min_length=1)
    occurred_on: date
    accuracy_ratio: float = Field(ge=0, le=1)
    first_pass_approved: bool
    rework_hours: float = Field(ge=0)
    verification_status: str
    source_version: int | None = Field(default=None, ge=0)
    source_updated_at: datetime | None = None


class PerformanceEvidenceDataset(BaseModel):
    employees: list[Employee]
    performance_targets: list[PerformanceTarget]
    work_outputs: list[WorkOutputEvidence]
    attendance_events: list[AttendanceComplianceEvidence]
    submission_events: list[SubmissionComplianceEvidence]
    leave_events: list[LeaveComplianceEvidence]
    quality_events: list[QualityEvidence]
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
    team: str | None
    role: str | None
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
    evidence_links: list[str] = Field(default_factory=list)
    validation_findings: list[ValidationFinding] = Field(default_factory=list)


class EvidenceResult(BaseModel):
    employee_id: str
    record_ids: list[str]
    evidence_links: list[str]
    findings: list[ValidationFinding]


class KpiTrendResult(BaseModel):
    employee_id: str
    employee_name: str | None
    baseline_overall_score: float | None
    current_overall_score: float | None
    overall_score_change: float | None
    baseline_status: str
    current_status: str


class KpiTrendPoint(BaseModel):
    period_start: date
    period_end: date
    employee_count: int = Field(ge=0)
    scored_employee_count: int = Field(ge=0)
    productivity_employee_count: int = Field(ge=0)
    compliance_employee_count: int = Field(ge=0)
    quality_employee_count: int = Field(ge=0)
    productivity_score: float | None
    compliance_score: float | None
    quality_score: float | None
    overall_score: float | None
    data_confidence: float | None
    record_count: int = Field(ge=0)


class PerformanceAlert(BaseModel):
    code: str
    severity: Literal["error", "warning", "info"]
    message: str
    employee_id: str | None
    employee_name: str | None
    team: str | None
    occurrence_count: int = Field(ge=1)
    record_ids: list[str]
    evidence_links: list[str] = Field(default_factory=list)
    scoring_impact: Literal[
        "blocks_score",
        "excluded_from_scoring",
        "lowers_confidence",
        "affects_score",
        "none",
    ]
