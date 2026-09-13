from dataclasses import dataclass
from datetime import date

from app.schemas.performance import (
    AttendanceComplianceEvidence,
    LeaveComplianceEvidence,
    PerformanceEvidenceDataset,
    QualityEvidence,
    SubmissionComplianceEvidence,
    ValidationFinding,
    WorkOutputEvidence,
)
from app.services.performance import metrics


@dataclass(frozen=True, slots=True)
class EmployeeEvidence:
    projects: list[WorkOutputEvidence]
    attendance: list[AttendanceComplianceEvidence]
    reports: list[SubmissionComplianceEvidence]
    reviews: list[QualityEvidence]
    leave: list[LeaveComplianceEvidence]


def duplicate_attendance_ids(findings: list[ValidationFinding]) -> set[str]:
    """Return duplicate attendance identities excluded by the scorer."""
    return {
        record_id
        for finding in findings
        if finding.code == "duplicate_attendance"
        for record_id in finding.record_ids[1:]
    }


def quality_excluded(record: QualityEvidence, known_output_ids: set[str]) -> bool:
    """A review is excluded only when its work output is absent from the full dataset."""
    return record.related_output_id not in known_output_ids


def employee_evidence(
    dataset: PerformanceEvidenceDataset,
    employee_id: str,
    start_date: date | None,
    end_date: date | None,
    duplicate_ids: set[str],
    *,
    include_excluded: bool = False,
) -> EmployeeEvidence:
    """Scope employee evidence using the scorer's dates, optionally retaining excluded rows."""
    known_output_ids = {output.record_id for output in dataset.work_outputs}
    return EmployeeEvidence(
        projects=metrics.in_period(
            dataset.work_outputs, employee_id, lambda row: row.assigned_date, start_date, end_date
        ),
        attendance=[
            row
            for row in metrics.in_period(
                dataset.attendance_events,
                employee_id,
                lambda row: row.occurred_on,
                start_date,
                end_date,
            )
            if include_excluded or row.record_id not in duplicate_ids
        ],
        reports=metrics.in_period(
            dataset.submission_events, employee_id, lambda row: row.due_date, start_date, end_date
        ),
        reviews=[
            row
            for row in metrics.in_period(
                dataset.quality_events,
                employee_id,
                lambda row: row.occurred_on,
                start_date,
                end_date,
            )
            if include_excluded or not quality_excluded(row, known_output_ids)
        ],
        leave=metrics.leave_in_period(dataset, employee_id, start_date, end_date),
    )
