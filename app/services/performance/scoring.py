from datetime import date

from app.schemas.performance import (
    KpiResult,
    PerformanceEvidenceDataset,
    ValidationFinding,
)
from app.services.performance.metrics import (
    _attendance_compliance,
    _evidence_confidence,
    _format_optional_score,
    _in_period,
    _leave_compliance,
    _performance_tier,
    _report_compliance,
    _weighted_available,
)
from app.services.performance.validation import validate_dataset

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
        completed = [
            record
            for record in projects
            if record.completion_status.casefold()
            in {"completed on time", "completed late"}
        ]
        project_target = target.target_outputs_90d
        if start_date is not None and end_date is not None:
            period_days = (end_date - start_date).days + 1
            project_target *= period_days / 90
        completion_score = min(100.0, len(completed) / project_target * 100)
        effort_records = [
            record for record in completed if record.actual_effort_hours is not None
        ]
        average_hours = (
            sum(
                record.actual_effort_hours
                for record in effort_records
                if record.actual_effort_hours is not None
            )
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
        attendance_breakdown = _attendance_compliance(
            attendance,
            dataset.mapped_fields.get("attendance_events", set()),
        )
        attendance_compliance = attendance_breakdown.score
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
        accuracy = (
            sum(review.accuracy_ratio for review in reviews) / len(reviews) * 100
            if reviews
            else 0
        )
        first_pass = (
            sum(review.first_pass_approved for review in reviews) / len(reviews) * 100
            if reviews
            else 0
        )
        rework = (
            max(
                0.0,
                100
                - (sum(review.rework_hours for review in reviews) / len(reviews) * 8),
            )
            if reviews
            else 0
        )
        quality = accuracy * 0.60 + first_pass * 0.25 + rework * 0.15
        confidence, confidence_reason = _evidence_confidence(
            projects,
            attendance,
            reports,
            reviews,
            dataset.mapped_fields.get("attendance_events", set()),
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
        record_ids = [
            *(record.record_id for record in projects),
            *(record.record_id for record in attendance),
            *(record.record_id for record in reports),
            *(record.record_id for record in reviews),
        ]
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
                    f"Weighted 50% attendance ({_format_optional_score(attendance_compliance)}: "
                    f"arrival {_format_optional_score(attendance_breakdown.arrival_score)}, "
                    f"shift end {_format_optional_score(attendance_breakdown.shift_end_score)}, "
                    f"lunch {_format_optional_score(attendance_breakdown.lunch_score)}), "
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

