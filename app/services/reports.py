from datetime import UTC, date, datetime, timedelta
from urllib.parse import urlparse

from app.core.errors import EmployeeReportNotFoundError, InvalidAnalysisFilterError
from app.schemas.reports import (
    EmployeeReportData,
    EmployeeReportPreviewResponse,
    EmployeeReportRequest,
    ReportFinding,
    ReportKpiSection,
    ReportPeriod,
)
from app.services.submissions import get_aggregated_dashboard


async def build_employee_report_preview(
    request: EmployeeReportRequest,
) -> EmployeeReportPreviewResponse:
    """Build a renderer-ready employee report from deterministic dashboard results."""
    try:
        dashboard = await get_aggregated_dashboard(
            employee_id=request.employee_id,
            period_weeks=request.period_weeks,
            start_date=request.start_date,
            end_date=request.end_date,
        )
    except InvalidAnalysisFilterError as exc:
        raise EmployeeReportNotFoundError(
            f"Employee '{request.employee_id}' is not available for this report."
        ) from exc
    if len(dashboard.results) != 1:
        raise EmployeeReportNotFoundError(
            f"Employee '{request.employee_id}' is not available for this report."
        )

    start_date = dashboard.applied_filters.start_date
    end_date = dashboard.applied_filters.end_date
    if start_date is None or end_date is None:
        raise EmployeeReportNotFoundError(
            "The selected employee has no reporting period to render."
        )

    employee = dashboard.results[0]
    prior_start, prior_end = _prior_period(
        start_date,
        end_date,
        dashboard.coverage_start,
    )
    prior_score: float | None = None
    if prior_start is not None and prior_end is not None:
        prior_dashboard = await get_aggregated_dashboard(
            employee_id=request.employee_id,
            start_date=prior_start,
            end_date=prior_end,
        )
        if prior_dashboard.results:
            prior_score = prior_dashboard.results[0].overall_score

    score_change = (
        round(employee.overall_score - prior_score, 2)
        if employee.overall_score is not None and prior_score is not None
        else None
    )
    findings = [
        ReportFinding(
            code=alert.code,
            severity=alert.severity,
            scoring_impact=alert.scoring_impact,
            message=alert.message,
            occurrence_count=alert.occurrence_count,
            record_ids=alert.record_ids,
            evidence_links=[
                link for link in alert.evidence_links if _is_safe_evidence_link(link)
            ],
        )
        for alert in dashboard.alerts
        if alert.employee_id == employee.employee_id
    ]

    report = EmployeeReportData(
        employee_id=employee.employee_id,
        employee_name=employee.employee_name,
        team=employee.team,
        role=employee.role,
        period=ReportPeriod(
            start_date=start_date,
            end_date=end_date,
            prior_start_date=prior_start,
            prior_end_date=prior_end,
        ),
        generated_at=datetime.now(UTC),
        overall_score=employee.overall_score,
        result_status=employee.result_status,
        performance_tier=employee.performance_tier,
        data_confidence=employee.data_confidence,
        confidence_threshold=employee.confidence_threshold,
        confidence_explanation=employee.confidence_reason,
        kpis=[
            ReportKpiSection(
                name="Productivity",
                score=employee.productivity_score,
                weight=35,
                explanation=employee.productivity_reason,
            ),
            ReportKpiSection(
                name="Compliance",
                score=employee.compliance_score,
                weight=30,
                explanation=employee.compliance_reason,
            ),
            ReportKpiSection(
                name="Quality",
                score=employee.quality_score,
                weight=35,
                explanation=employee.quality_reason,
            ),
        ],
        trends=dashboard.trends,
        prior_overall_score=prior_score,
        overall_score_change=score_change,
        findings=findings,
        supporting_record_ids=employee.supporting_record_ids,
        metric_definitions=[
            "Productivity: completion and time efficiency (35% of overall).",
            "Compliance: attendance, reports, and leave compliance (30% of overall).",
            "Quality: accuracy, first-pass approval, and rework (35% of overall).",
        ],
        manager_review_notice=(
            "This report supports coaching and manager review. It must not be used alone "
            "to make hiring, termination, promotion, compensation, or disciplinary decisions."
        ),
    )
    return EmployeeReportPreviewResponse(report=report)


def _prior_period(
    start_date: date,
    end_date: date,
    coverage_start: date | None,
) -> tuple[date | None, date | None]:
    period_days = (end_date - start_date).days + 1
    prior_end = start_date - timedelta(days=1)
    prior_start = prior_end - timedelta(days=period_days - 1)
    if coverage_start is None or prior_start < coverage_start:
        return None, None
    return prior_start, prior_end


def _is_safe_evidence_link(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)
