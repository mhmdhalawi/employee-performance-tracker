from datetime import date, timedelta

from app.schemas.performance import (
    KpiTrendPoint,
    PerformanceEvidenceDataset,
)
from app.services.performance.overview import inspect_dataset
from app.services.performance.scoring import calculate_kpis
from app.services.performance.validation import validate_dataset
from app.utils.numbers import average


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
        compliance_ids = (
            {
                record.employee_id
                for record in dataset.attendance_events
                if record.employee_id in result_ids
                and week_start <= record.occurred_on <= week_end
            }
            | {
                report.employee_id
                for report in dataset.submission_events
                if report.employee_id in result_ids
                and week_start <= report.due_date <= week_end
            }
            | {
                request.employee_id
                for request in dataset.leave_events
                if request.employee_id in result_ids
                and request.end_date >= week_start
                and request.start_date <= week_end
            }
        )
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
                productivity_score=average(
                    result.productivity_score
                    for result in results
                    if result.employee_id in productivity_ids
                ),
                compliance_score=average(
                    result.compliance_score
                    for result in results
                    if result.employee_id in compliance_ids
                ),
                quality_score=average(
                    result.quality_score
                    for result in results
                    if result.employee_id in quality_ids
                ),
                overall_score=average(
                    result.overall_score
                    for result in scored
                    if result.overall_score is not None
                ),
                data_confidence=average(result.data_confidence for result in results),
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
