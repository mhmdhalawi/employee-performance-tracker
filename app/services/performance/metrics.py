from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from app.schemas.performance import (
    AttendanceComplianceEvidence,
    PerformanceEvidenceDataset,
    QualityEvidence,
    SubmissionComplianceEvidence,
    WorkOutputEvidence,
)
from app.services.performance.constants import (
    REQUIRED_EVIDENCE_MATRIX,
    _NEUTRAL_ATTENDANCE_OUTCOMES,
)

@dataclass(frozen=True, slots=True)
class AttendanceBreakdown:
    score: float | None
    arrival_score: float | None
    shift_end_score: float | None
    lunch_score: float | None

class EmployeeLinkedRecord(Protocol):
    employee_id: str


def _in_period[T: EmployeeLinkedRecord](
    records: list[T],
    employee_id: str,
    date_getter: Callable[[T], date],
    start_date: date | None,
    end_date: date | None,
) -> list[T]:
    """Filter employee-linked records to an optional inclusive date range."""
    return [
        record
        for record in records
        if record.employee_id == employee_id
        and (start_date is None or date_getter(record) >= start_date)
        and (end_date is None or date_getter(record) <= end_date)
    ]


def _attendance_compliance(
    records: list[AttendanceComplianceEvidence],
    mapped_fields: set[str],
) -> AttendanceBreakdown:
    working_records = [
        record
        for record in records
        if record.outcome.casefold() not in _NEUTRAL_ATTENDANCE_OUTCOMES
    ]
    arrival_score = (
        _boolean_score(
            record.actual_start <= record.scheduled_start
            for record in working_records
            if record.scheduled_start is not None and record.actual_start is not None
        )
        if {"scheduled_start", "actual_start"} <= mapped_fields
        else None
    )
    shift_end_score = (
        _boolean_score(
            record.actual_end >= record.scheduled_end
            for record in working_records
            if record.scheduled_end is not None and record.actual_end is not None
        )
        if {"scheduled_end", "actual_end"} <= mapped_fields
        else None
    )
    lunch_score = (
        _boolean_score(
            record.lunch_in > record.lunch_out
            for record in working_records
            if record.lunch_out is not None and record.lunch_in is not None
        )
        if {"lunch_out", "lunch_in"} <= mapped_fields
        else None
    )
    return AttendanceBreakdown(
        score=_weighted_available_optional(
            [(arrival_score, 1), (shift_end_score, 1), (lunch_score, 1)]
        ),
        arrival_score=arrival_score,
        shift_end_score=shift_end_score,
        lunch_score=lunch_score,
    )


def _report_compliance(reports: list[SubmissionComplianceEvidence]) -> float | None:
    supported: list[tuple[date, date]] = []
    for report in reports:
        submitted_date = report.submitted_date
        if (
            submitted_date is not None
            and report.verification_status.casefold() == "verified"
        ):
            supported.append((submitted_date, report.due_date))
    if not supported:
        return None
    return (
        sum(submitted_date <= due_date for submitted_date, due_date in supported)
        / len(supported)
        * 100
    )


def _leave_compliance(
    dataset: PerformanceEvidenceDataset,
    employee_id: str,
    start_date: date | None,
    end_date: date | None,
) -> float:
    requests = [
        request
        for request in dataset.leave_events
        if request.employee_id == employee_id
        and (start_date is None or request.end_date >= start_date)
        and (end_date is None or request.start_date <= end_date)
    ]
    sick_requests = [
        request for request in requests if request.category.casefold() == "sick leave"
    ]
    if not sick_requests:
        return 100
    return (
        sum(
            request.outcome.casefold() == "approved" and request.documentation_complete
            for request in sick_requests
        )
        / len(sick_requests)
        * 100
    )


def _performance_tier(overall: float | None) -> str | None:
    if overall is None:
        return None
    if overall >= 90:
        return "Top performer"
    if overall >= 80:
        return "Strong"
    if overall >= 70:
        return "Solid"
    return "Needs support"


def _evidence_confidence(
    projects: list[WorkOutputEvidence],
    attendance: list[AttendanceComplianceEvidence],
    reports: list[SubmissionComplianceEvidence],
    reviews: list[QualityEvidence],
    mapped_attendance_fields: set[str],
) -> tuple[float, str]:
    project_confidence = _coverage(
        record.verification_status.casefold() == "verified"
        and (
            record.completion_status.casefold()
            not in {"completed on time", "completed late"}
            or record.actual_effort_hours is not None
        )
        for record in projects
    )
    attendance_confidence = _coverage(
        _attendance_evidence_complete(record, mapped_attendance_fields)
        for record in attendance
    )
    report_confidence = _coverage(
        report.submitted_date is not None
        and report.verification_status.casefold() == "verified"
        for report in reports
    )
    quality_confidence = _coverage(
        review.verification_status.casefold() == "verified" for review in reviews
    )
    coverage = {
        "productivity": project_confidence,
        "attendance": attendance_confidence,
        "submissions": report_confidence,
        "quality": quality_confidence,
    }
    confidence = min(coverage.values())
    required = "; ".join(
        f"{kpi}: {', '.join(fields)}"
        for kpi, fields in REQUIRED_EVIDENCE_MATRIX.items()
    )
    reason = (
        "Evidence coverage by required source: "
        + ", ".join(f"{source} {value:.2f}%" for source, value in coverage.items())
        + f"; confidence is the lowest required-source coverage. Required evidence: {required}."
    )
    return confidence, reason


def _coverage(checks: Iterable[bool]) -> float:
    values = list(checks)
    return sum(values) / len(values) * 100 if values else 0.0


def _boolean_score(checks: Iterable[bool]) -> float | None:
    values = list(checks)
    return sum(values) / len(values) * 100 if values else None


def _average(values: Iterable[float]) -> float | None:
    available = list(values)
    return round(sum(available) / len(available), 2) if available else None


def _weighted_available(
    components: list[tuple[float | None, float]],
) -> float:
    available = [(value, weight) for value, weight in components if value is not None]
    if not available:
        return 0.0
    total_weight = sum(weight for _, weight in available)
    return sum(value * weight for value, weight in available) / total_weight


def _weighted_available_optional(
    components: list[tuple[float | None, float]],
) -> float | None:
    available = [(value, weight) for value, weight in components if value is not None]
    if not available:
        return None
    total_weight = sum(weight for _, weight in available)
    return sum(value * weight for value, weight in available) / total_weight


def _format_optional_score(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "unavailable"


def _attendance_evidence_complete(
    record: AttendanceComplianceEvidence,
    mapped_fields: set[str],
) -> bool:
    if record.outcome.casefold() in _NEUTRAL_ATTENDANCE_OUTCOMES:
        return True
    required_fields = {"actual_end"}
    for field_group in (
        {"scheduled_start", "actual_start"},
        {"scheduled_end", "actual_end"},
        {"lunch_out", "lunch_in"},
    ):
        if field_group & mapped_fields:
            required_fields.update(field_group)
    return all(
        getattr(record, field_name) is not None for field_name in required_fields
    )

