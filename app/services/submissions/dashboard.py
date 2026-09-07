from datetime import date, datetime, timedelta

from app.core.errors import DashboardNotFoundError, InvalidAnalysisFilterError
from app.database import load_aggregation_state
from app.schemas.uploads import (
    CalculationPlan,
    DashboardResponse,
    EmployeeFilterOption,
)
from app.services.agent import build_analysis_response
from app.services.aggregation import materialize_aggregation
from app.services.performance import inspect_dataset

async def get_aggregated_dashboard(
    employee_id: str | None = None,
    team: str | None = None,
    period_weeks: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> DashboardResponse:
    """Recalculate one filtered dashboard from canonical cross-submission evidence."""
    if period_weeks is not None and (start_date is not None or end_date is not None):
        raise InvalidAnalysisFilterError(
            "period_weeks cannot be combined with start_date or end_date."
        )
    if (
        period_weeks is not None
        and period_weeks != 4
        and period_weeks != 8
        and period_weeks != 12
    ):
        raise InvalidAnalysisFilterError("period_weeks must be 4, 8, or 12.")
    if start_date is not None and end_date is not None and start_date > end_date:
        raise InvalidAnalysisFilterError("start_date must be on or before end_date.")

    state = load_aggregation_state()
    if state is None:
        raise DashboardNotFoundError("No completed data submission is available.")
    materialized = materialize_aggregation(state)
    dataset = materialized.dataset
    overview = inspect_dataset(dataset)

    effective_start = start_date
    effective_end = end_date
    if period_weeks is not None and overview.date_end is not None:
        effective_end = overview.date_end
        preset_start = effective_end - timedelta(days=period_weeks * 7 - 1)
        effective_start = max(
            preset_start,
            overview.date_start or preset_start,
        )

    first_plan = CalculationPlan(
        selected_tables=materialized.mapping_summaries[0].selected_tables,
        table_classifications=materialized.mapping_summaries[0].table_classifications,
    )
    classifications = [
        classification
        for summary in materialized.mapping_summaries
        for classification in summary.table_classifications
    ]
    response = build_analysis_response(
        dataset,
        first_plan,
        import_issues=[],
        employee_id=employee_id,
        team=team,
        start_date=effective_start,
        end_date=effective_end,
        period_weeks=period_weeks,
        additional_limitations=materialized.limitations,
        limitation_classifications=classifications,
        model="deterministic-aggregation",
        mapping_cache_hit=True,
    )
    available_employees = sorted(
        (
            EmployeeFilterOption(
                employee_id=employee.employee_id,
                employee_name=employee.employee_name,
                team=employee.team,
            )
            for employee in dataset.employees
        ),
        key=lambda item: (
            (item.employee_name or item.employee_id).casefold(),
            item.employee_id,
        ),
    )
    return DashboardResponse(
        results=response.results,
        summary=response.summary,
        dataset_overview=response.dataset_overview,
        applied_filters=response.applied_filters,
        available_employees=available_employees,
        available_teams=overview.teams,
        trends=response.trends,
        alerts=response.alerts,
        import_issues=response.import_issues,
        validation_summary=response.validation_summary,
        global_validation_findings=response.global_validation_findings,
        limitations=response.limitations,
        coverage_start=overview.date_start,
        coverage_end=overview.date_end,
        included_submission_count=state.included_submission_count,
        latest_submission_at=datetime.fromisoformat(state.latest_submission_at),
        mapping_summaries=materialized.mapping_summaries,
    )
