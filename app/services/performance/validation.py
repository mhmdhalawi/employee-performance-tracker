from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import date

from app.schemas.performance import (
    AttendanceComplianceEvidence,
    PerformanceEvidenceDataset,
    ValidationFinding,
    ValidationSummary,
)
from app.services.performance.constants import _NEUTRAL_ATTENDANCE_OUTCOMES

def validate_dataset(dataset: PerformanceEvidenceDataset) -> list[ValidationFinding]:
    """Find scoring-relevant data quality issues without discarding their evidence."""
    findings: list[ValidationFinding] = []
    employee_ids = {employee.employee_id for employee in dataset.employees}
    known_outputs = {record.record_id for record in dataset.work_outputs}
    known_targets = {target.employee_id for target in dataset.performance_targets}

    duplicate_employee_ids = _duplicates(
        employee.employee_id for employee in dataset.employees
    )
    for duplicate_employee_id in duplicate_employee_ids:
        findings.append(
            ValidationFinding(
                code="duplicate_employee_id",
                severity="error",
                message="Employee IDs must be unique before KPI calculation.",
                employee_id=duplicate_employee_id,
                record_ids=[duplicate_employee_id],
                source_type="employees",
                scoring_impact="blocks_score",
            )
        )

    records = [
        *dataset.work_outputs,
        *dataset.attendance_events,
        *dataset.submission_events,
        *dataset.leave_events,
        *dataset.quality_events,
    ]
    duplicate_record_ids = _duplicates(record.record_id for record in records)
    for duplicate_record_id in duplicate_record_ids:
        affected_employee_ids = sorted(
            {
                record.employee_id
                for record in records
                if record.record_id == duplicate_record_id
            }
        )
        for affected_employee_id in affected_employee_ids:
            findings.append(
                ValidationFinding(
                    code="duplicate_record_id",
                    severity="error",
                    message="Source record IDs must be unique before KPI calculation.",
                    employee_id=affected_employee_id,
                    record_ids=[duplicate_record_id],
                    source_type="source_records",
                    scoring_impact="blocks_score",
                )
            )

    for employee_id in sorted(employee_ids - known_targets):
        findings.append(
            ValidationFinding(
                code="missing_performance_target",
                severity="error",
                message="The employee has no KPI target and cannot receive a deterministic score.",
                employee_id=employee_id,
                record_ids=[employee_id],
                source_type="performance_targets",
                scoring_impact="blocks_score",
            )
        )

    for target in dataset.performance_targets:
        if target.employee_id not in employee_ids:
            findings.append(
                _orphan("KPI target", target.employee_id, target.employee_id)
            )

    attendance_by_key: dict[tuple[str, date], list[str]] = defaultdict(list)
    mapped_attendance_fields = dataset.mapped_fields.get("attendance_events", set())
    for record in dataset.attendance_events:
        attendance_by_key[record.employee_id, record.occurred_on].append(
            record.record_id
        )
        if record.employee_id not in employee_ids:
            findings.append(
                _orphan("attendance evidence", record.record_id, record.employee_id)
            )
        if record.outcome.casefold() not in _NEUTRAL_ATTENDANCE_OUTCOMES:
            required_fields = {"actual_end"}
            for field_group in (
                {"scheduled_start", "actual_start"},
                {"scheduled_end", "actual_end"},
                {"lunch_out", "lunch_in"},
            ):
                if field_group & mapped_attendance_fields:
                    required_fields.update(field_group)
            for field_name in sorted(required_fields):
                if getattr(record, field_name) is None:
                    findings.append(_missing_attendance_finding(record, field_name))
    for (employee_id, _), record_ids in attendance_by_key.items():
        if len(record_ids) > 1:
            findings.append(
                ValidationFinding(
                    code="duplicate_attendance",
                    severity="warning",
                    message="Multiple attendance records share the same employee and work date; exclude duplicates before scoring.",
                    employee_id=employee_id,
                    record_ids=record_ids,
                    source_type="attendance",
                    scoring_impact="excluded_from_scoring",
                )
            )

    for record in dataset.work_outputs:
        if record.employee_id not in employee_ids:
            findings.append(
                _orphan("work output", record.record_id, record.employee_id)
            )
        if record.verification_status.casefold() != "verified":
            findings.append(
                ValidationFinding(
                    code="missing_productivity_evidence",
                    severity="warning",
                    message="Productivity evidence is not verified and cannot support confidence.",
                    employee_id=record.employee_id,
                    record_ids=[record.record_id],
                    source_type="productivity_evidence",
                    scoring_impact="lowers_confidence",
                )
            )
        if (
            record.completion_status.casefold()
            in {"completed on time", "completed late"}
            and record.actual_effort_hours is None
        ):
            findings.append(
                ValidationFinding(
                    code="missing_actual_effort",
                    severity="warning",
                    message="Completed work has no actual effort hours and lowers evidence confidence.",
                    employee_id=record.employee_id,
                    record_ids=[record.record_id],
                    source_type="productivity_evidence",
                    scoring_impact="lowers_confidence",
                )
            )
        if (
            record.completion_status.casefold() == "overdue"
            and record.completed_date is None
        ):
            findings.append(
                ValidationFinding(
                    code="overdue_work_output",
                    severity="info",
                    message="Work output is overdue and uncompleted; show a productivity risk.",
                    employee_id=record.employee_id,
                    record_ids=[record.record_id],
                    source_type="productivity_evidence",
                    scoring_impact="affects_score",
                )
            )

    for report in dataset.submission_events:
        if report.employee_id not in employee_ids:
            findings.append(
                _orphan("submission evidence", report.record_id, report.employee_id)
            )
        if report.submitted_date is None:
            findings.append(
                ValidationFinding(
                    code="missing_submission",
                    severity="warning",
                    message="Required submission has no submission date and lowers evidence confidence.",
                    employee_id=report.employee_id,
                    record_ids=[report.record_id],
                    source_type="submission_evidence",
                    scoring_impact="lowers_confidence",
                )
            )
        if (
            report.submitted_date is not None
            and report.verification_status.casefold() != "verified"
        ):
            findings.append(
                ValidationFinding(
                    code="missing_submission_evidence",
                    severity="warning",
                    message="Submission evidence is not verified and cannot support confidence.",
                    employee_id=report.employee_id,
                    record_ids=[report.record_id],
                    source_type="submission_evidence",
                    scoring_impact="lowers_confidence",
                )
            )
        if (
            report.submitted_date is not None
            and report.verification_status.casefold() == "verified"
            and report.submitted_date > report.due_date
        ):
            findings.append(
                ValidationFinding(
                    code="late_submission",
                    severity="info",
                    message="Verified submission date is after its due date and affects report compliance.",
                    employee_id=report.employee_id,
                    record_ids=[report.record_id],
                    source_type="submission_evidence",
                    scoring_impact="affects_score",
                )
            )

    for leave_request in dataset.leave_events:
        if leave_request.employee_id not in employee_ids:
            findings.append(
                _orphan(
                    "leave evidence", leave_request.record_id, leave_request.employee_id
                )
            )
        if (
            leave_request.category.casefold() == "sick leave"
            and leave_request.outcome.casefold() == "approved"
            and not leave_request.documentation_complete
        ):
            findings.append(
                ValidationFinding(
                    code="incomplete_sick_leave_documentation",
                    severity="warning",
                    message="Approved sick leave is missing required documentation and affects leave compliance.",
                    employee_id=leave_request.employee_id,
                    record_ids=[leave_request.record_id],
                    source_type="leave_evidence",
                    scoring_impact="affects_score",
                )
            )

    for review in dataset.quality_events:
        if review.employee_id not in employee_ids:
            findings.append(
                _orphan("quality evidence", review.record_id, review.employee_id)
            )
        if review.related_output_id not in known_outputs:
            findings.append(
                ValidationFinding(
                    code="orphan_quality_evidence",
                    severity="error",
                    message="Quality evidence references a work output that is not in the dataset.",
                    employee_id=review.employee_id,
                    record_ids=[review.record_id, review.related_output_id],
                    source_type="quality_evidence",
                    scoring_impact="excluded_from_scoring",
                )
            )
        if review.accuracy_ratio < 0.75:
            findings.append(
                ValidationFinding(
                    code="low_accuracy",
                    severity="info",
                    message="Quality review accuracy is below 75%; recommend quality coaching.",
                    employee_id=review.employee_id,
                    record_ids=[review.record_id],
                    source_type="quality_evidence",
                    scoring_impact="affects_score",
                )
            )
        if review.verification_status.casefold() != "verified":
            findings.append(
                ValidationFinding(
                    code="missing_quality_evidence",
                    severity="warning",
                    message="Quality-review evidence is not verified and cannot support confidence.",
                    employee_id=review.employee_id,
                    record_ids=[review.record_id],
                    source_type="quality_evidence",
                    scoring_impact="lowers_confidence",
                )
            )
    return findings


def summarize_validation(findings: list[ValidationFinding]) -> ValidationSummary:
    """Summarize validation severity, exclusions, and affected employees."""
    excluded_record_count = sum(
        max(0, len(finding.record_ids) - 1)
        if finding.code == "duplicate_attendance"
        else 1
        for finding in findings
        if finding.scoring_impact == "excluded_from_scoring"
    )
    return ValidationSummary(
        total_findings=len(findings),
        error_count=sum(finding.severity == "error" for finding in findings),
        warning_count=sum(finding.severity == "warning" for finding in findings),
        info_count=sum(finding.severity == "info" for finding in findings),
        excluded_record_count=excluded_record_count,
        affected_employee_count=len(
            {finding.employee_id for finding in findings if finding.employee_id}
        ),
    )

def _missing_attendance_finding(
    record: AttendanceComplianceEvidence,
    field_name: str,
) -> ValidationFinding:
    labels = {
        "scheduled_start": "scheduled start time",
        "actual_start": "actual arrival time",
        "lunch_out": "lunch check-out time",
        "lunch_in": "lunch return time",
        "scheduled_end": "scheduled end time",
        "actual_end": "actual end time",
    }
    return ValidationFinding(
        code=f"missing_{field_name}",
        severity="warning",
        message=(
            f"Attendance record has no {labels[field_name]} and lowers evidence confidence."
        ),
        employee_id=record.employee_id,
        record_ids=[record.record_id],
        source_type="attendance",
        scoring_impact="lowers_confidence",
    )


def _duplicates(values: Iterable[str]) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)


def _orphan(record_type: str, record_id: str, employee_id: str) -> ValidationFinding:
    return ValidationFinding(
        code="orphan_record",
        severity="error",
        message=f"{record_type.capitalize()} references an employee that is not in the dataset.",
        employee_id=employee_id,
        record_ids=[record_id, employee_id],
        source_type=record_type,
        scoring_impact="excluded_from_scoring",
    )

