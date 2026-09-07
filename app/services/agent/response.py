from datetime import date
from typing import Literal

from app.core.config import get_settings
from app.core.errors import InvalidAnalysisFilterError
from app.schemas.performance import (
    EmployeeKpiScores,
    KpiResult,
    PerformanceEvidenceDataset,
    ValidationFinding,
)
from app.schemas.uploads import (
    AnalysisFilters,
    AnalysisResponse,
    AnalysisSummary,
    CalculationPlan,
    ImportIssue,
    TableClassification,
)
from app.services.performance import (
    build_performance_alerts,
    calculate_kpis,
    calculate_weekly_kpi_trends,
    inspect_dataset,
    summarize_validation,
    validate_dataset,
)

def build_analysis_response(
    performance_dataset: PerformanceEvidenceDataset,
    analysis: CalculationPlan,
    import_issues: list[ImportIssue],
    employee_id: str | None = None,
    team: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    period_weeks: Literal[4, 8, 12] | None = None,
    additional_validation_findings: list[ValidationFinding] | None = None,
    additional_limitations: list[str] | None = None,
    limitation_classifications: list[TableClassification] | None = None,
    model: str | None = None,
    total_tokens: int = 0,
    model_requests: int = 0,
    mapping_cache_hit: bool = True,
) -> AnalysisResponse:
    """Construct one deterministic response from a validated evidence dataset."""
    validation_findings = [
        *validate_dataset(performance_dataset),
        *(additional_validation_findings or []),
    ]
    overview = inspect_dataset(performance_dataset)
    available_teams = overview.teams
    if team and team.casefold() not in {value.casefold() for value in available_teams}:
        raise InvalidAnalysisFilterError(f"Unknown team '{team}'.")
    known_employee_ids = {
        employee.employee_id for employee in performance_dataset.employees
    }
    if employee_id and employee_id not in known_employee_ids:
        raise InvalidAnalysisFilterError(f"Unknown employee_id '{employee_id}'.")
    effective_start: date | None = None
    effective_end: date | None = None
    if start_date or end_date:
        effective_start = start_date or overview.date_start
        effective_end = end_date or overview.date_end
    kpi_results = calculate_kpis(
        performance_dataset,
        employee_id=employee_id,
        team=team,
        start_date=effective_start,
        end_date=effective_end,
        validation_findings=validation_findings,
    )
    result_employee_ids = {kpi.employee_id for kpi in kpi_results}
    employee_by_id = {
        employee.employee_id: employee for employee in performance_dataset.employees
    }
    included_record_ids = {
        record_id
        for result in kpi_results
        for record_id in result.supporting_record_ids
    }
    scoped_findings = [
        finding
        for finding in validation_findings
        if (
            finding.employee_id in result_employee_ids
            and (
                finding.scoring_impact == "blocks_score"
                or not finding.record_ids
                or bool(set(finding.record_ids) & included_record_ids)
            )
        )
        or finding.employee_id not in known_employee_ids
    ]
    project_links = {
        record.record_id: record.evidence_link
        for record in performance_dataset.work_outputs
        if record.evidence_link
    }
    employee_results = [
        EmployeeKpiScores(
            employee_id=kpi.employee_id,
            employee_name=kpi.employee_name,
            team=employee_by_id[kpi.employee_id].team,
            role=employee_by_id[kpi.employee_id].role,
            productivity_score=kpi.productivity_score,
            productivity_reason=kpi.productivity_reason,
            compliance_score=kpi.compliance_score,
            compliance_reason=kpi.compliance_reason,
            quality_score=kpi.quality_score,
            quality_reason=kpi.quality_reason,
            data_confidence=kpi.data_confidence,
            confidence_threshold=kpi.confidence_threshold,
            confidence_reason=kpi.confidence_reason,
            overall_score=kpi.overall_score,
            result_status=kpi.result_status,
            performance_tier=kpi.performance_tier,
            supporting_record_ids=kpi.supporting_record_ids,
            evidence_links=sorted(
                {
                    project_links[record_id]
                    for record_id in kpi.supporting_record_ids
                    if record_id in project_links
                }
            ),
            validation_findings=[
                finding
                for finding in scoped_findings
                if finding.employee_id == kpi.employee_id
            ],
        )
        for kpi in kpi_results
    ]
    alerts = build_performance_alerts(
        performance_dataset,
        scoped_findings,
        result_employee_ids,
        included_record_ids,
    )
    limitations = _build_limitations(
        performance_dataset,
        limitation_classifications or analysis.table_classifications,
        import_issues,
        scoped_findings,
    )
    limitations.extend(additional_limitations or [])
    return AnalysisResponse(
        results=employee_results,
        summary=_build_analysis_summary(kpi_results),
        dataset_overview=overview,
        applied_filters=AnalysisFilters(
            employee_id=employee_id,
            team=team,
            start_date=effective_start or overview.date_start,
            end_date=effective_end or overview.date_end,
            period_weeks=period_weeks,
        ),
        available_teams=available_teams,
        trends=calculate_weekly_kpi_trends(
            performance_dataset,
            start_date=start_date,
            end_date=end_date,
            employee_id=employee_id,
            team=team,
        ),
        alerts=alerts,
        import_issues=import_issues,
        validation_summary=summarize_validation(scoped_findings),
        global_validation_findings=[
            finding
            for finding in scoped_findings
            if finding.employee_id not in known_employee_ids
        ],
        selected_tables=analysis.selected_tables,
        table_classifications=analysis.table_classifications,
        limitations=limitations,
        model=model or get_settings().openai_model,
        total_tokens=total_tokens,
        model_requests=model_requests,
        mapping_cache_hit=mapping_cache_hit,
    )


def _build_analysis_summary(kpi_results: list[KpiResult]) -> AnalysisSummary:
    insufficient_ids = [
        result.employee_id
        for result in kpi_results
        if result.result_status == "Insufficient data"
    ]
    tier_counts: dict[str, int] = {}
    for result in kpi_results:
        if result.performance_tier is not None:
            tier_counts[result.performance_tier] = (
                tier_counts.get(result.performance_tier, 0) + 1
            )

    total_count = len(kpi_results)
    insufficient_count = len(insufficient_ids)
    scored_count = total_count - insufficient_count
    scored_overall = [
        result.overall_score
        for result in kpi_results
        if result.overall_score is not None
    ]
    narrative = (
        f"Analyzed {total_count} employees. {scored_count} received an overall "
        f"performance result; {insufficient_count} were marked Insufficient data "
        "because their evidence confidence was below the configured threshold."
    )
    return AnalysisSummary(
        total_employee_count=total_count,
        scored_employee_count=scored_count,
        insufficient_data_count=insufficient_count,
        insufficient_data_employee_ids=insufficient_ids,
        performance_tier_counts=dict(sorted(tier_counts.items())),
        average_overall_score=_average(scored_overall),
        average_productivity_score=_average(
            [result.productivity_score for result in kpi_results]
        ),
        average_compliance_score=_average(
            [result.compliance_score for result in kpi_results]
        ),
        average_quality_score=_average(
            [result.quality_score for result in kpi_results]
        ),
        narrative=narrative,
    )


def _average(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None

def _build_limitations(
    dataset: PerformanceEvidenceDataset,
    classifications: list[TableClassification],
    import_issues: list[ImportIssue],
    validation_findings: list[ValidationFinding],
) -> list[str]:
    limitations: list[str] = []
    uncertain_sources = sorted(
        classification.source_name
        for classification in classifications
        if classification.confidence != "high"
    )
    if uncertain_sources:
        limitations.append(
            "Classification confidence was below high for: "
            + ", ".join(uncertain_sources)
            + "."
        )
    if import_issues:
        limitations.append(
            f"{len(import_issues)} source rows or calculator bindings could not be imported."
        )
    mapped_attendance = dataset.mapped_fields.get("attendance_events", set())
    attendance_capabilities = {
        "arrival": {"scheduled_start", "actual_start"},
        "shift-end": {"scheduled_end", "actual_end"},
        "lunch": {"lunch_out", "lunch_in"},
    }
    unavailable_attendance_checks = [
        label
        for label, required_fields in attendance_capabilities.items()
        if dataset.attendance_events and not required_fields <= mapped_attendance
    ]
    if unavailable_attendance_checks:
        limitations.append(
            "Attendance checks unavailable because their timestamp fields were not mapped: "
            + ", ".join(unavailable_attendance_checks)
            + "."
        )
    excluded_count = summarize_validation(validation_findings).excluded_record_count
    if excluded_count:
        limitations.append(
            f"{excluded_count} invalid or duplicate records were excluded from scoring."
        )
    return limitations

