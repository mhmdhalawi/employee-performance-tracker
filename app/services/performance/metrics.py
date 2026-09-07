from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, time
from typing import Protocol

from app.schemas.performance import (
    AttendanceComplianceEvidence,
    PerformanceEvidenceDataset,
    QualityEvidence,
    SubmissionComplianceEvidence,
    WorkOutputEvidence,
)
from app.services.performance.constants import (
    COMPLETED_OUTPUT_STATUSES,
    NEUTRAL_ATTENDANCE_OUTCOMES,
    REQUIRED_EVIDENCE_MATRIX,
)


@dataclass(frozen=True, slots=True)
class AttendanceBreakdown:
    score: float | None
    arrival_score: float | None
    shift_end_score: float | None
    lunch_score: float | None


class EmployeeLinkedRecord(Protocol):
    employee_id: str


def in_period[T: EmployeeLinkedRecord](
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


def attendance_compliance(
    records: list[AttendanceComplianceEvidence],
    mapped_fields: set[str],
) -> AttendanceBreakdown:
    working_records = [
        record
        for record in records
        if record.outcome.casefold() not in NEUTRAL_ATTENDANCE_OUTCOMES
    ]
    arrival_score = _mapped_pair_score(
        working_records,
        mapped_fields,
        ("scheduled_start", "actual_start"),
        lambda scheduled_start, actual_start: actual_start <= scheduled_start,
    )
    shift_end_score = _mapped_pair_score(
        working_records,
        mapped_fields,
        ("scheduled_end", "actual_end"),
        lambda scheduled_end, actual_end: actual_end >= scheduled_end,
    )
    lunch_score = _mapped_pair_score(
        working_records,
        mapped_fields,
        ("lunch_out", "lunch_in"),
        lambda lunch_out, lunch_in: lunch_in > lunch_out,
    )
    return AttendanceBreakdown(
        score=_weighted_available_optional(
            [(arrival_score, 1), (shift_end_score, 1), (lunch_score, 1)]
        ),
        arrival_score=arrival_score,
        shift_end_score=shift_end_score,
        lunch_score=lunch_score,
    )


def _mapped_pair_score(
    records: list[AttendanceComplianceEvidence],
    mapped_fields: set[str],
    fields: tuple[str, str],
    is_compliant: Callable[[time, time], bool],
) -> float | None:
    """Score one attendance time pair, or None when the source did not map both fields."""
    if not set(fields) <= mapped_fields:
        return None
    first_name, second_name = fields
    pairs = [
        (getattr(record, first_name), getattr(record, second_name)) for record in records
    ]
    return _boolean_score(
        is_compliant(first, second)
        for first, second in pairs
        if first is not None and second is not None
    )


def required_attendance_fields(mapped_fields: set[str]) -> set[str]:
    """Return the fields a working attendance record must supply for the mapped pairs."""
    required = {"actual_end"}
    for field_pair in (
        {"scheduled_start", "actual_start"},
        {"scheduled_end", "actual_end"},
        {"lunch_out", "lunch_in"},
    ):
        if field_pair & mapped_fields:
            required.update(field_pair)
    return required


def report_compliance(reports: list[SubmissionComplianceEvidence]) -> float | None:
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


def leave_compliance(
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


def performance_tier(overall: float | None) -> str | None:
    if overall is None:
        return None
    if overall >= 90:
        return "Top performer"
    if overall >= 80:
        return "Strong"
    if overall >= 70:
        return "Solid"
    return "Needs support"


def evidence_confidence(
    projects: list[WorkOutputEvidence],
    attendance: list[AttendanceComplianceEvidence],
    reports: list[SubmissionComplianceEvidence],
    reviews: list[QualityEvidence],
    mapped_attendance_fields: set[str],
) -> tuple[float, str]:
    project_confidence = _coverage(
        record.verification_status.casefold() == "verified"
        and (
            record.completion_status.casefold() not in COMPLETED_OUTPUT_STATUSES
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


def _boolean_score(checks: Iterable[bool]) -> float | None:
    """Return the percentage of checks that passed, or None when there are none."""
    values = list(checks)
    if not values:
        return None
    return sum(values) / len(values) * 100


def _coverage(checks: Iterable[bool]) -> float:
    """Return the percentage of checks that passed, treating no evidence as no coverage."""
    score = _boolean_score(checks)
    return score if score is not None else 0.0


def _weighted_available_optional(
    components: list[tuple[float | None, float]],
) -> float | None:
    """Combine the available components by weight, or None when none are available."""
    available = [(value, weight) for value, weight in components if value is not None]
    if not available:
        return None
    total_weight = sum(weight for _, weight in available)
    return sum(value * weight for value, weight in available) / total_weight


def weighted_available(
    components: list[tuple[float | None, float]],
) -> float:
    """Combine the available components by weight, scoring zero when none are available."""
    score = _weighted_available_optional(components)
    return score if score is not None else 0.0


def format_optional_score(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "unavailable"


def _attendance_evidence_complete(
    record: AttendanceComplianceEvidence,
    mapped_fields: set[str],
) -> bool:
    if record.outcome.casefold() in NEUTRAL_ATTENDANCE_OUTCOMES:
        return True
    return all(
        getattr(record, field_name) is not None
        for field_name in required_attendance_fields(mapped_fields)
    )

