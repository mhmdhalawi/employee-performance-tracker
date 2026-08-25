from collections import defaultdict
from collections.abc import Callable
from datetime import date
from typing import Protocol

from app.schemas.performance import (
    AttendanceRecord,
    DatasetOverview,
    EvidenceResult,
    KpiResult,
    KpiTrendResult,
    PerformanceDataset,
    Report,
    ValidationFinding,
)


def inspect_dataset(dataset: PerformanceDataset) -> DatasetOverview:
    """Return the available population, coverage period, and source record counts."""
    dates = [
        *[project.assigned_date for project in dataset.projects],
        *[record.work_date for record in dataset.attendance],
        *[report.due_date for report in dataset.reports],
        *[review.review_date for review in dataset.quality_reviews],
    ]
    return DatasetOverview(
        employee_count=len(dataset.employees),
        date_start=min(dates) if dates else None,
        date_end=max(dates) if dates else None,
        record_counts={
            "projects": len(dataset.projects),
            "attendance": len(dataset.attendance),
            "reports": len(dataset.reports),
            "leave_requests": len(dataset.leave_requests),
            "quality_reviews": len(dataset.quality_reviews),
        },
        teams=sorted({employee.team for employee in dataset.employees if employee.team}),
    )


def validate_dataset(dataset: PerformanceDataset) -> list[ValidationFinding]:
    """Find scoring-relevant data quality issues without discarding their evidence."""
    findings: list[ValidationFinding] = []
    employee_ids = {employee.employee_id for employee in dataset.employees}
    known_projects = {project.project_id for project in dataset.projects}
    known_targets = {target.employee_id for target in dataset.kpi_targets}

    for employee_id in sorted(employee_ids - known_targets):
        findings.append(
            ValidationFinding(
                code="missing_kpi_target",
                message="The employee has no KPI target and cannot receive a deterministic score.",
                employee_id=employee_id,
                record_ids=[employee_id],
            )
        )

    attendance_by_key: dict[tuple[str, date], list[str]] = defaultdict(list)
    for record in dataset.attendance:
        attendance_by_key[record.employee_id, record.work_date].append(record.attendance_id)
        if record.employee_id not in employee_ids:
            findings.append(_orphan("attendance", record.attendance_id, record.employee_id))
        if not record.actual_end and record.arrival_status.casefold() not in {"annual leave", "sick leave"}:
            findings.append(
                ValidationFinding(
                    code="missing_actual_end",
                    message="Attendance record has no actual end time; confidence is reduced.",
                    employee_id=record.employee_id,
                    record_ids=[record.attendance_id],
                )
            )
    for (employee_id, _), record_ids in attendance_by_key.items():
        if len(record_ids) > 1:
            findings.append(
                ValidationFinding(
                    code="duplicate_attendance",
                    message="Multiple attendance records share the same employee and work date; exclude duplicates before scoring.",
                    employee_id=employee_id,
                    record_ids=record_ids,
                )
            )

    for project in dataset.projects:
        if project.employee_id not in employee_ids:
            findings.append(_orphan("project", project.project_id, project.employee_id))
        if project.evidence_status.casefold() != "verified":
            findings.append(
                ValidationFinding(
                    code="missing_project_evidence",
                    message="Project evidence is not verified and cannot support confidence.",
                    employee_id=project.employee_id,
                    record_ids=[project.project_id],
                )
            )
        if project.project_status.casefold() == "overdue" and project.completed_date is None:
            findings.append(
                ValidationFinding(
                    code="overdue_project",
                    message="Project is overdue and uncompleted; show a productivity risk.",
                    employee_id=project.employee_id,
                    record_ids=[project.project_id],
                )
            )

    for report in dataset.reports:
        if report.employee_id not in employee_ids:
            findings.append(_orphan("report", report.report_id, report.employee_id))
        if report.submitted_date is None:
            findings.append(
                ValidationFinding(
                    code="missing_report",
                    message="Required report has no submission date and counts against report compliance.",
                    employee_id=report.employee_id,
                    record_ids=[report.report_id],
                )
            )

    for review in dataset.quality_reviews:
        if review.employee_id not in employee_ids:
            findings.append(_orphan("quality review", review.review_id, review.employee_id))
        if review.project_id not in known_projects:
            findings.append(
                ValidationFinding(
                    code="orphan_quality_review",
                    message="Quality review references a project that is not in the dataset.",
                    employee_id=review.employee_id,
                    record_ids=[review.review_id, review.project_id],
                )
            )
        if review.accuracy_pct < 0.75:
            findings.append(
                ValidationFinding(
                    code="low_accuracy",
                    message="Quality review accuracy is below 75%; recommend quality coaching.",
                    employee_id=review.employee_id,
                    record_ids=[review.review_id],
                )
            )
    return findings


def calculate_kpis(
    dataset: PerformanceDataset,
    employee_id: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[KpiResult]:
    """Calculate deterministic KPI results for the requested employees and period."""
    target_by_employee = {target.employee_id: target for target in dataset.kpi_targets}
    duplicate_ids = {
        record_id
        for finding in validate_dataset(dataset)
        if finding.code == "duplicate_attendance"
        for record_id in finding.record_ids[1:]
    }
    results: list[KpiResult] = []
    for employee in dataset.employees:
        if employee_id and employee.employee_id != employee_id:
            continue
        target = target_by_employee.get(employee.employee_id)
        if target is None:
            continue
        projects = _in_period(
            dataset.projects,
            employee.employee_id,
            lambda project: project.assigned_date,
            start_date,
            end_date,
        )
        attendance = [
            record
            for record in _in_period(
                dataset.attendance,
                employee.employee_id,
                lambda record: record.work_date,
                start_date,
                end_date,
            )
            if record.attendance_id not in duplicate_ids
        ]
        reports = _in_period(
            dataset.reports,
            employee.employee_id,
            lambda report: report.due_date,
            start_date,
            end_date,
        )
        reviews = _in_period(
            dataset.quality_reviews,
            employee.employee_id,
            lambda review: review.review_date,
            start_date,
            end_date,
        )
        completed = [project for project in projects if project.project_status.casefold() in {"completed on time", "completed late"}]
        completion_score = min(100.0, len(completed) / target.target_projects_90d * 100)
        average_hours = sum(project.actual_hours or 0 for project in completed) / len(completed) if completed else 0
        time_score = min(100.0, target.target_avg_hours / average_hours * 100) if average_hours else 0
        productivity = completion_score * 0.60 + time_score * 0.40
        attendance_compliance = _attendance_compliance(attendance)
        report_compliance = _report_compliance(reports)
        leave_compliance = _leave_compliance(dataset, employee.employee_id)
        compliance = attendance_compliance * 0.50 + report_compliance * 0.35 + leave_compliance * 0.15
        accuracy = sum(review.accuracy_pct for review in reviews) / len(reviews) * 100 if reviews else 0
        first_pass = sum(review.first_pass_approved for review in reviews) / len(reviews) * 100 if reviews else 0
        rework = max(0.0, 100 - (sum(review.rework_hours for review in reviews) / len(reviews) * 8)) if reviews else 0
        quality = accuracy * 0.60 + first_pass * 0.25 + rework * 0.15
        confidence = sum(project.evidence_status.casefold() == "verified" for project in projects) / len(projects) * 100 if projects else 0
        overall = productivity * 0.35 + compliance * 0.30 + quality * 0.35 if confidence >= target.minimum_confidence * 100 else None
        status = _status(overall, confidence, target.minimum_confidence * 100)
        record_ids = [*(project.project_id for project in projects), *(record.attendance_id for record in attendance), *(report.report_id for report in reports), *(review.review_id for review in reviews)]
        results.append(KpiResult(employee_id=employee.employee_id, employee_name=employee.employee_name, productivity_score=round(productivity, 2), compliance_score=round(compliance, 2), quality_score=round(quality, 2), data_confidence=round(confidence, 2), overall_score=round(overall, 2) if overall is not None else None, result_status=status, supporting_record_ids=record_ids))
    return results


def get_supporting_evidence(dataset: PerformanceDataset, employee_id: str) -> EvidenceResult:
    """Return records, evidence links, and validation findings supporting an employee result."""
    findings = [finding for finding in validate_dataset(dataset) if finding.employee_id == employee_id]
    projects = [project for project in dataset.projects if project.employee_id == employee_id]
    record_ids = [*(project.project_id for project in projects), *(record.attendance_id for record in dataset.attendance if record.employee_id == employee_id), *(report.report_id for report in dataset.reports if report.employee_id == employee_id), *(review.review_id for review in dataset.quality_reviews if review.employee_id == employee_id)]
    return EvidenceResult(employee_id=employee_id, record_ids=record_ids, evidence_links=[project.evidence_link for project in projects if project.evidence_link], findings=findings)


def calculate_kpi_trends(
    dataset: PerformanceDataset,
    baseline_start: date,
    baseline_end: date,
    current_start: date,
    current_end: date,
    employee_id: str | None = None,
) -> list[KpiTrendResult]:
    """Compare deterministic overall KPI results across two explicit periods."""
    baseline = {result.employee_id: result for result in calculate_kpis(dataset, employee_id, baseline_start, baseline_end)}
    current = {result.employee_id: result for result in calculate_kpis(dataset, employee_id, current_start, current_end)}
    trends: list[KpiTrendResult] = []
    for result in current.values():
        baseline_result = baseline.get(result.employee_id)
        if baseline_result is None:
            continue
        baseline_score = baseline_result.overall_score
        current_score = result.overall_score
        score_change = (
            round(current_score - baseline_score, 2)
            if current_score is not None and baseline_score is not None
            else None
        )
        trends.append(
            KpiTrendResult(
                employee_id=result.employee_id,
                employee_name=result.employee_name,
                baseline_overall_score=baseline_score,
                current_overall_score=current_score,
                overall_score_change=score_change,
                baseline_status=baseline_result.result_status,
                current_status=result.result_status,
            )
        )
    return trends


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


def _attendance_compliance(records: list[AttendanceRecord]) -> float:
    if not records:
        return 0
    compliant = {"on time", "annual leave", "sick leave"}
    return sum(record.arrival_status.casefold() in compliant for record in records) / len(records) * 100


def _report_compliance(reports: list[Report]) -> float:
    return sum(report.submission_status.casefold() == "submitted on time" for report in reports) / len(reports) * 100 if reports else 0


def _leave_compliance(dataset: PerformanceDataset, employee_id: str) -> float:
    requests = [request for request in dataset.leave_requests if request.employee_id == employee_id]
    return sum(request.request_status.casefold() == "approved" for request in requests) / len(requests) * 100 if requests else 100


def _status(overall: float | None, confidence: float, minimum_confidence: float) -> str:
    if confidence < minimum_confidence:
        return "Insufficient data"
    if overall is None:
        return "Insufficient data"
    if overall >= 90:
        return "Top performer"
    if overall >= 80:
        return "Strong"
    if overall >= 70:
        return "Solid"
    return "Needs support"


def _orphan(record_type: str, record_id: str, employee_id: str) -> ValidationFinding:
    return ValidationFinding(code="orphan_record", message=f"{record_type.capitalize()} references an employee that is not in the dataset.", employee_id=employee_id, record_ids=[record_id, employee_id])
