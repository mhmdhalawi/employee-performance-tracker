from dataclasses import dataclass
from datetime import date

from app.schemas.performance import (
    AttendanceComplianceEvidence,
    KpiResult,
    PerformanceEvidenceDataset,
    PerformanceTarget,
    QualityEvidence,
    SubmissionComplianceEvidence,
    ValidationFinding,
    WorkOutputEvidence,
)
from app.services.performance import metrics
from app.services.performance.validation import validate_dataset

_COMPLETED_STATUSES = {"completed on time", "completed late"}


@dataclass(frozen=True, slots=True)
class ScoredKpi:
    score: float
    reason: str


@dataclass(frozen=True, slots=True)
class EmployeeEvidence:
    projects: list[WorkOutputEvidence]
    attendance: list[AttendanceComplianceEvidence]
    reports: list[SubmissionComplianceEvidence]
    reviews: list[QualityEvidence]


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

        evidence = _employee_evidence(
            dataset,
            employee.employee_id,
            start_date,
            end_date,
            duplicate_ids,
        )
        productivity = _score_productivity(
            evidence.projects,
            target,
            start_date,
            end_date,
        )
        compliance = _score_compliance(
            dataset,
            employee.employee_id,
            evidence.attendance,
            evidence.reports,
            start_date,
            end_date,
        )
        quality = _score_quality(evidence.reviews)
        confidence, confidence_reason = metrics.evidence_confidence(
            evidence.projects,
            evidence.attendance,
            evidence.reports,
            evidence.reviews,
            dataset.mapped_fields.get("attendance_events", set()),
        )
        confidence_threshold = target.minimum_confidence * 100
        score_is_allowed = (
            confidence >= confidence_threshold
            and employee.employee_id not in blocking_employee_ids
        )
        overall = (
            productivity.score * 0.35 + compliance.score * 0.30 + quality.score * 0.35
            if score_is_allowed
            else None
        )
        performance_tier = (
            metrics.performance_tier(overall) if score_is_allowed else None
        )
        results.append(
            KpiResult(
                employee_id=employee.employee_id,
                employee_name=employee.employee_name,
                productivity_score=round(productivity.score, 2),
                productivity_reason=productivity.reason,
                compliance_score=round(compliance.score, 2),
                compliance_reason=compliance.reason,
                quality_score=round(quality.score, 2),
                quality_reason=quality.reason,
                data_confidence=round(confidence, 2),
                confidence_threshold=round(confidence_threshold, 2),
                confidence_reason=confidence_reason,
                overall_score=round(overall, 2) if overall is not None else None,
                result_status=performance_tier or "Insufficient data",
                performance_tier=performance_tier,
                supporting_record_ids=_supporting_record_ids(evidence),
            )
        )
    return results


def _employee_evidence(
    dataset: PerformanceEvidenceDataset,
    employee_id: str,
    start_date: date | None,
    end_date: date | None,
    duplicate_ids: set[str],
) -> EmployeeEvidence:
    """Scope every evidence collection to one employee and the requested period."""
    attendance = [
        record
        for record in metrics.in_period(
            dataset.attendance_events,
            employee_id,
            lambda record: record.occurred_on,
            start_date,
            end_date,
        )
        if record.record_id not in duplicate_ids
    ]
    reviews = metrics.in_period(
        dataset.quality_events,
        employee_id,
        lambda review: review.occurred_on,
        start_date,
        end_date,
    )
    # A review only counts as evidence when the work output it grades is present.
    known_output_ids = {record.record_id for record in dataset.work_outputs}
    return EmployeeEvidence(
        projects=metrics.in_period(
            dataset.work_outputs,
            employee_id,
            lambda project: project.assigned_date,
            start_date,
            end_date,
        ),
        attendance=attendance,
        reports=metrics.in_period(
            dataset.submission_events,
            employee_id,
            lambda report: report.due_date,
            start_date,
            end_date,
        ),
        reviews=[
            review for review in reviews if review.related_output_id in known_output_ids
        ],
    )


def _score_productivity(
    projects: list[WorkOutputEvidence],
    target: PerformanceTarget,
    start_date: date | None,
    end_date: date | None,
) -> ScoredKpi:
    """Weight output completion at 60% and effort-target time efficiency at 40%."""
    completed = [
        record
        for record in projects
        if record.completion_status.casefold() in _COMPLETED_STATUSES
    ]
    project_target = target.target_outputs_90d
    if start_date is not None and end_date is not None:
        # The 90-day output target is prorated to the requested reporting period.
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
    return ScoredKpi(
        score=metrics.weighted_available(
            [(completion_score, 0.60), (time_score, 0.40)]
        ),
        reason=(
            f"Weighted 60% completion ({completion_score:.2f}) and 40% "
            f"time efficiency ({metrics.format_optional_score(time_score)}); {len(completed)} completed "
            f"work outputs against a target of {project_target:.2f}, "
            f"averaging {metrics.format_optional_score(average_hours)} hours against a target of "
            f"{target.target_avg_effort_hours:g}."
        ),
    )


def _score_compliance(
    dataset: PerformanceEvidenceDataset,
    employee_id: str,
    attendance: list[AttendanceComplianceEvidence],
    reports: list[SubmissionComplianceEvidence],
    start_date: date | None,
    end_date: date | None,
) -> ScoredKpi:
    """Weight attendance at 50%, report submission at 35%, and leave compliance at 15%."""
    breakdown = metrics.attendance_compliance(
        attendance,
        dataset.mapped_fields.get("attendance_events", set()),
    )
    report_score = metrics.report_compliance(reports)
    leave_score = metrics.leave_compliance(
        dataset,
        employee_id,
        start_date,
        end_date,
    )
    return ScoredKpi(
        score=metrics.weighted_available(
            [
                (breakdown.score, 0.50),
                (report_score, 0.35),
                (leave_score, 0.15),
            ]
        ),
        reason=(
            f"Weighted 50% attendance ({metrics.format_optional_score(breakdown.score)}: "
            f"arrival {metrics.format_optional_score(breakdown.arrival_score)}, "
            f"shift end {metrics.format_optional_score(breakdown.shift_end_score)}, "
            f"lunch {metrics.format_optional_score(breakdown.lunch_score)}), "
            f"35% reporting ({metrics.format_optional_score(report_score)}), and 15% leave "
            f"compliance ({leave_score:.2f}) after excluding duplicate "
            "attendance records."
        ),
    )


def _score_quality(reviews: list[QualityEvidence]) -> ScoredKpi:
    """Weight accuracy at 60%, first-pass approval at 25%, and rework at 15%."""
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
    # Rework is inverted into a score: eight average rework hours exhaust the component.
    rework = (
        max(
            0.0,
            100 - (sum(review.rework_hours for review in reviews) / len(reviews) * 8),
        )
        if reviews
        else 0
    )
    return ScoredKpi(
        score=accuracy * 0.60 + first_pass * 0.25 + rework * 0.15,
        reason=(
            f"Weighted 60% accuracy ({accuracy:.2f}), 25% first-pass approval "
            f"({first_pass:.2f}), and 15% rework ({rework:.2f}) across "
            f"{len(reviews)} quality reviews."
        ),
    )


def _supporting_record_ids(evidence: EmployeeEvidence) -> list[str]:
    return [
        *(record.record_id for record in evidence.projects),
        *(record.record_id for record in evidence.attendance),
        *(record.record_id for record in evidence.reports),
        *(record.record_id for record in evidence.reviews),
    ]
