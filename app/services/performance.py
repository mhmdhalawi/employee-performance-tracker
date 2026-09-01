from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from datetime import date, timedelta
from typing import Protocol

from app.schemas.performance import (
    AttendanceComplianceEvidence,
    DatasetOverview,
    EvidenceResult,
    KpiResult,
    KpiTrendPoint,
    KpiTrendResult,
    PerformanceAlert,
    PerformanceEvidenceDataset,
    QualityEvidence,
    SubmissionComplianceEvidence,
    ValidationFinding,
    ValidationSummary,
    WorkOutputEvidence,
)


REQUIRED_EVIDENCE_MATRIX: dict[str, tuple[str, ...]] = {
    "productivity": (
        "verified completion status",
        "actual effort hours for completed work",
    ),
    "compliance": (
        "attendance check-out unless on approved leave",
        "submitted date and verified report evidence",
    ),
    "quality": (
        "verified accuracy",
        "first-pass result",
        "rework hours",
    ),
}


def inspect_dataset(dataset: PerformanceEvidenceDataset) -> DatasetOverview:
    """Return the available population, coverage period, and source record counts."""
    dates = [
        *[record.assigned_date for record in dataset.work_outputs],
        *[record.occurred_on for record in dataset.attendance_events],
        *[record.due_date for record in dataset.submission_events],
        *[record.occurred_on for record in dataset.quality_events],
    ]
    return DatasetOverview(
        employee_count=len(dataset.employees),
        date_start=min(dates) if dates else None,
        date_end=max(dates) if dates else None,
        record_counts={
            "productivity_evidence": len(dataset.work_outputs),
            "attendance_compliance_evidence": len(dataset.attendance_events),
            "submission_compliance_evidence": len(dataset.submission_events),
            "leave_compliance_evidence": len(dataset.leave_events),
            "quality_evidence": len(dataset.quality_events),
        },
        teams=sorted({employee.team for employee in dataset.employees if employee.team}),
    )


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
            {record.employee_id for record in records if record.record_id == duplicate_record_id}
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
            findings.append(_orphan("KPI target", target.employee_id, target.employee_id))

    attendance_by_key: dict[tuple[str, date], list[str]] = defaultdict(list)
    for record in dataset.attendance_events:
        attendance_by_key[record.employee_id, record.occurred_on].append(record.record_id)
        if record.employee_id not in employee_ids:
            findings.append(_orphan("attendance evidence", record.record_id, record.employee_id))
        if not record.actual_end and record.outcome.casefold() not in {
            "annual leave",
            "sick leave",
        }:
            findings.append(
                ValidationFinding(
                    code="missing_actual_end",
                    severity="warning",
                    message="Attendance record has no actual end time and lowers evidence confidence.",
                    employee_id=record.employee_id,
                    record_ids=[record.record_id],
                    source_type="attendance",
                    scoring_impact="lowers_confidence",
                )
            )
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
            findings.append(_orphan("work output", record.record_id, record.employee_id))
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
        if record.completion_status.casefold() == "overdue" and record.completed_date is None:
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
            findings.append(_orphan("submission evidence", report.record_id, report.employee_id))
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

    for leave_request in dataset.leave_events:
        if leave_request.employee_id not in employee_ids:
            findings.append(
                _orphan("leave evidence", leave_request.record_id, leave_request.employee_id)
            )

    for review in dataset.quality_events:
        if review.employee_id not in employee_ids:
            findings.append(_orphan("quality evidence", review.record_id, review.employee_id))
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


def calculate_kpis(
    dataset: PerformanceEvidenceDataset,
    employee_id: str | None = None,
    team: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    validation_findings: list[ValidationFinding] | None = None,
) -> list[KpiResult]:
    """Calculate deterministic KPI results for the requested employees and period."""
    target_by_employee = {
        target.employee_id: target for target in dataset.performance_targets
    }
    findings = (
        validation_findings
        if validation_findings is not None
        else validate_dataset(dataset)
    )
    duplicate_ids = {
        record_id
        for finding in findings
        if finding.code == "duplicate_attendance"
        for record_id in finding.record_ids[1:]
    }
    blocking_employee_ids = {
        finding.employee_id
        for finding in findings
        if finding.scoring_impact == "blocks_score" and finding.employee_id
    }
    results: list[KpiResult] = []
    processed_employee_ids: set[str] = set()
    for employee in dataset.employees:
        if employee.employee_id in processed_employee_ids:
            continue
        processed_employee_ids.add(employee.employee_id)
        if employee_id and employee.employee_id != employee_id:
            continue
        if team and (employee.team or "").casefold() != team.casefold():
            continue
        target = target_by_employee.get(employee.employee_id)
        if target is None:
            continue
        projects = _in_period(
            dataset.work_outputs,
            employee.employee_id,
            lambda project: project.assigned_date,
            start_date,
            end_date,
        )
        attendance = [
            record
            for record in _in_period(
                dataset.attendance_events,
                employee.employee_id,
                lambda record: record.occurred_on,
                start_date,
                end_date,
            )
            if record.record_id not in duplicate_ids
        ]
        reports = _in_period(
            dataset.submission_events,
            employee.employee_id,
            lambda report: report.due_date,
            start_date,
            end_date,
        )
        reviews = _in_period(
            dataset.quality_events,
            employee.employee_id,
            lambda review: review.occurred_on,
            start_date,
            end_date,
        )
        known_output_ids = {record.record_id for record in dataset.work_outputs}
        reviews = [
            review for review in reviews if review.related_output_id in known_output_ids
        ]
        completed = [record for record in projects if record.completion_status.casefold() in {"completed on time", "completed late"}]
        project_target = target.target_outputs_90d
        if start_date is not None and end_date is not None:
            period_days = (end_date - start_date).days + 1
            project_target *= period_days / 90
        completion_score = min(100.0, len(completed) / project_target * 100)
        effort_records = [
            record for record in completed if record.actual_effort_hours is not None
        ]
        average_hours = (
            sum(record.actual_effort_hours for record in effort_records if record.actual_effort_hours is not None)
            / len(effort_records)
            if effort_records
            else None
        )
        time_score = (
            min(100.0, target.target_avg_effort_hours / average_hours * 100)
            if average_hours
            else None
        )
        productivity = _weighted_available(
            [(completion_score, 0.60), (time_score, 0.40)]
        )
        attendance_compliance = _attendance_compliance(attendance)
        report_compliance = _report_compliance(reports)
        leave_compliance = _leave_compliance(
            dataset,
            employee.employee_id,
            start_date,
            end_date,
        )
        compliance = _weighted_available(
            [
                (attendance_compliance, 0.50),
                (report_compliance, 0.35),
                (leave_compliance, 0.15),
            ]
        )
        accuracy = sum(review.accuracy_ratio for review in reviews) / len(reviews) * 100 if reviews else 0
        first_pass = sum(review.first_pass_approved for review in reviews) / len(reviews) * 100 if reviews else 0
        rework = max(0.0, 100 - (sum(review.rework_hours for review in reviews) / len(reviews) * 8)) if reviews else 0
        quality = accuracy * 0.60 + first_pass * 0.25 + rework * 0.15
        confidence, confidence_reason = _evidence_confidence(
            projects,
            attendance,
            reports,
            reviews,
        )
        confidence_threshold = target.minimum_confidence * 100
        score_is_allowed = (
            confidence >= confidence_threshold
            and employee.employee_id not in blocking_employee_ids
        )
        overall = (
            productivity * 0.35 + compliance * 0.30 + quality * 0.35
            if score_is_allowed
            else None
        )
        performance_tier = _performance_tier(overall) if score_is_allowed else None
        status = performance_tier or "Insufficient data"
        record_ids = [*(record.record_id for record in projects), *(record.record_id for record in attendance), *(record.record_id for record in reports), *(record.record_id for record in reviews)]
        results.append(
            KpiResult(
                employee_id=employee.employee_id,
                employee_name=employee.employee_name,
                productivity_score=round(productivity, 2),
                productivity_reason=(
                    f"Weighted 60% completion ({completion_score:.2f}) and 40% "
                    f"time efficiency ({_format_optional_score(time_score)}); {len(completed)} completed "
                    f"work outputs against a target of {project_target:.2f}, "
                    f"averaging {_format_optional_score(average_hours)} hours against a target of "
                    f"{target.target_avg_effort_hours:g}."
                ),
                compliance_score=round(compliance, 2),
                compliance_reason=(
                    f"Weighted 50% attendance ({attendance_compliance:.2f}), "
                    f"35% reporting ({_format_optional_score(report_compliance)}), and 15% leave "
                    f"compliance ({leave_compliance:.2f}) after excluding duplicate "
                    "attendance records."
                ),
                quality_score=round(quality, 2),
                quality_reason=(
                    f"Weighted 60% accuracy ({accuracy:.2f}), 25% first-pass approval "
                    f"({first_pass:.2f}), and 15% rework ({rework:.2f}) across "
                    f"{len(reviews)} quality reviews."
                ),
                data_confidence=round(confidence, 2),
                confidence_threshold=round(confidence_threshold, 2),
                confidence_reason=confidence_reason,
                overall_score=round(overall, 2) if overall is not None else None,
                result_status=status,
                performance_tier=performance_tier,
                supporting_record_ids=record_ids,
            )
        )
    return results


def calculate_weekly_kpi_trends(
    dataset: PerformanceEvidenceDataset,
    start_date: date | None = None,
    end_date: date | None = None,
    employee_id: str | None = None,
    team: str | None = None,
) -> list[KpiTrendPoint]:
    """Return cumulative weekly KPI points for one consistently filtered population."""
    overview = inspect_dataset(dataset)
    period_start = start_date or overview.date_start
    period_end = end_date or overview.date_end
    if period_start is None or period_end is None or period_start > period_end:
        return []

    periods: list[tuple[date, date]] = []
    week_start = period_start
    while week_start <= period_end:
        week_end = min(week_start + timedelta(days=6), period_end)
        periods.append((week_start, week_end))
        week_start = week_end + timedelta(days=1)

    findings = validate_dataset(dataset)
    points: list[KpiTrendPoint] = []
    for week_start, week_end in periods[-12:]:
        results = calculate_kpis(
            dataset,
            employee_id=employee_id,
            team=team,
            start_date=week_start,
            end_date=week_end,
            validation_findings=findings,
        )
        result_ids = {result.employee_id for result in results}
        productivity_ids = {
            record.employee_id
            for record in dataset.work_outputs
            if record.employee_id in result_ids
            and week_start <= record.assigned_date <= week_end
        }
        compliance_ids = {
            record.employee_id
            for record in dataset.attendance_events
            if record.employee_id in result_ids
            and week_start <= record.occurred_on <= week_end
        } | {
            report.employee_id
            for report in dataset.submission_events
            if report.employee_id in result_ids
            and week_start <= report.due_date <= week_end
        } | {
            request.employee_id
            for request in dataset.leave_events
            if request.employee_id in result_ids
            and request.end_date >= week_start
            and request.start_date <= week_end
        }
        quality_ids = {
            review.employee_id
            for review in dataset.quality_events
            if review.employee_id in result_ids
            and week_start <= review.occurred_on <= week_end
        }
        scored = [result for result in results if result.overall_score is not None]
        points.append(
            KpiTrendPoint(
                period_start=week_start,
                period_end=week_end,
                employee_count=len(results),
                scored_employee_count=len(scored),
                productivity_employee_count=len(productivity_ids),
                compliance_employee_count=len(compliance_ids),
                quality_employee_count=len(quality_ids),
                productivity_score=_average(
                    result.productivity_score
                    for result in results
                    if result.employee_id in productivity_ids
                ),
                compliance_score=_average(
                    result.compliance_score
                    for result in results
                    if result.employee_id in compliance_ids
                ),
                quality_score=_average(
                    result.quality_score
                    for result in results
                    if result.employee_id in quality_ids
                ),
                overall_score=_average(
                    result.overall_score
                    for result in scored
                    if result.overall_score is not None
                ),
                data_confidence=_average(
                    result.data_confidence for result in results
                ),
                record_count=len(
                    {
                        record_id
                        for result in results
                        for record_id in result.supporting_record_ids
                    }
                ),
            )
        )
    return points


def build_performance_alerts(
    dataset: PerformanceEvidenceDataset,
    findings: list[ValidationFinding],
    included_employee_ids: set[str],
    included_record_ids: set[str],
) -> list[PerformanceAlert]:
    """Convert relevant validation findings into traceable dashboard alerts."""
    employee_by_id = {
        employee.employee_id: employee for employee in dataset.employees
    }
    project_links = {
        record.record_id: record.evidence_link
        for record in dataset.work_outputs
        if record.evidence_link
    }
    severity_order = {"error": 0, "warning": 1, "info": 2}
    relevant = [
        finding
        for finding in findings
        if finding.employee_id in included_employee_ids
        and (
            not finding.record_ids
            or bool(set(finding.record_ids) & included_record_ids)
        )
    ]
    grouped: dict[
        tuple[str | None, str, str, str, str],
        list[ValidationFinding],
    ] = defaultdict(list)
    for finding in relevant:
        grouped[
            (
                finding.employee_id,
                finding.code,
                finding.severity,
                finding.message,
                finding.scoring_impact,
            )
        ].append(finding)

    alerts = [
        PerformanceAlert(
            code=code,
            severity=severity,
            message=message,
            employee_id=group_employee_id,
            employee_name=(
                employee_by_id[group_employee_id].employee_name
                if group_employee_id in employee_by_id
                else None
            ),
            team=(
                employee_by_id[group_employee_id].team
                if group_employee_id in employee_by_id
                else None
            ),
            occurrence_count=len(group_findings),
            record_ids=sorted(
                {
                    record_id
                    for finding in group_findings
                    for record_id in finding.record_ids
                }
            ),
            evidence_links=sorted(
                {
                project_links[record_id]
                for finding in group_findings
                for record_id in finding.record_ids
                if record_id in project_links
                }
            ),
            scoring_impact=scoring_impact,
        )
        for (
            group_employee_id,
            code,
            severity,
            message,
            scoring_impact,
        ), group_findings in grouped.items()
    ]
    return sorted(
        alerts,
        key=lambda alert: (
            severity_order[alert.severity],
            alert.employee_id or "",
            alert.code,
        ),
    )


def get_supporting_evidence(dataset: PerformanceEvidenceDataset, employee_id: str) -> EvidenceResult:
    """Return records, evidence links, and validation findings supporting an employee result."""
    findings = [finding for finding in validate_dataset(dataset) if finding.employee_id == employee_id]
    outputs = [record for record in dataset.work_outputs if record.employee_id == employee_id]
    record_ids = [*(record.record_id for record in outputs), *(record.record_id for record in dataset.attendance_events if record.employee_id == employee_id), *(record.record_id for record in dataset.submission_events if record.employee_id == employee_id), *(record.record_id for record in dataset.quality_events if record.employee_id == employee_id)]
    return EvidenceResult(employee_id=employee_id, record_ids=record_ids, evidence_links=[record.evidence_link for record in outputs if record.evidence_link], findings=findings)


def calculate_kpi_trends(
    dataset: PerformanceEvidenceDataset,
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


def _attendance_compliance(records: list[AttendanceComplianceEvidence]) -> float:
    if not records:
        return 0
    compliant = {"on time", "annual leave", "sick leave"}
    return sum(record.outcome.casefold() in compliant for record in records) / len(records) * 100


def _report_compliance(reports: list[SubmissionComplianceEvidence]) -> float | None:
    supported = [
        report
        for report in reports
        if report.submitted_date is not None
        and report.verification_status.casefold() == "verified"
    ]
    if not supported:
        return None
    return (
        sum(report.outcome.casefold() == "submitted on time" for report in supported)
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
    return sum(request.outcome.casefold() == "approved" for request in requests) / len(requests) * 100 if requests else 100


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
        bool(record.actual_end)
        or record.outcome.casefold() in {"annual leave", "sick leave"}
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
    reason = "Evidence coverage by required source: " + ", ".join(
        f"{source} {value:.2f}%" for source, value in coverage.items()
    ) + f"; confidence is the lowest required-source coverage. Required evidence: {required}."
    return confidence, reason


def _coverage(checks: Iterable[bool]) -> float:
    values = list(checks)
    return sum(values) / len(values) * 100 if values else 0.0


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


def _format_optional_score(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "unavailable"


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
