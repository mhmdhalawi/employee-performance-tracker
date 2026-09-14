from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.schemas.performance import (
    AttendanceComplianceEvidence,
    Employee,
    LeaveComplianceEvidence,
    QualityEvidence,
    SubmissionComplianceEvidence,
    ValidationFinding,
    WorkOutputEvidence,
)
from app.schemas.uploads import AnalysisFilters

type EvidenceKpi = Literal["productivity", "compliance", "quality"]


class EvidenceRow(BaseModel):
    record_id: str
    validation_findings: list[ValidationFinding]
    excluded_from_scoring: bool = False
    exclusion_reason: str | None = None


class WorkOutputRow(EvidenceRow):
    record_type: Literal["work_output"] = "work_output"
    record: WorkOutputEvidence


class AttendanceRow(EvidenceRow):
    record_type: Literal["attendance"] = "attendance"
    record: AttendanceComplianceEvidence


class SubmissionRow(EvidenceRow):
    record_type: Literal["submission"] = "submission"
    record: SubmissionComplianceEvidence


class LeaveRow(EvidenceRow):
    record_type: Literal["leave"] = "leave"
    record: LeaveComplianceEvidence


class QualityRow(EvidenceRow):
    record_type: Literal["quality"] = "quality"
    record: QualityEvidence


type ComplianceRow = Annotated[
    AttendanceRow | SubmissionRow | LeaveRow, Field(discriminator="record_type")
]
type EmployeeEvidenceRow = Annotated[
    WorkOutputRow | AttendanceRow | SubmissionRow | LeaveRow | QualityRow,
    Field(discriminator="record_type"),
]


class EvidenceTable[Row](BaseModel):
    total_count: int = Field(ge=0)
    rows: list[Row]


class EmployeeEvidenceTables(BaseModel):
    productivity: EvidenceTable[WorkOutputRow]
    compliance: EvidenceTable[ComplianceRow]
    quality: EvidenceTable[QualityRow]


class EmployeeEvidenceResponse(BaseModel):
    employee: Employee
    kpi: EvidenceKpi
    applied_filters: AnalysisFilters
    latest_submission_at: datetime
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=50)
    total_count: int = Field(ge=0)
    all_records_count: int = Field(ge=0)
    needs_review_count: int = Field(ge=0)
    review_only: bool = False
    rows: list[EmployeeEvidenceRow]
