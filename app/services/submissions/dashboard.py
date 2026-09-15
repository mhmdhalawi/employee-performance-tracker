from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.core.errors import DashboardNotFoundError
from app.database import StoredAggregationState, load_aggregation_state
from app.schemas.uploads import (
    CalculationPlan,
    DashboardResponse,
    EmployeeFilterOption,
)
from app.services.aggregation import MaterializedAggregation, materialize_aggregation
from app.services.analysis import build_analysis_response
from app.services.filters import (
    available_period_overlap,
    rolling_period_start,
    validate_analysis_period,
)
from app.services.performance import inspect_dataset


@dataclass(frozen=True, slots=True)
class DashboardContext:
    state: StoredAggregationState
    materialized: MaterializedAggregation


def load_dashboard_context() -> DashboardContext:
    """Load one coherent canonical state for dashboard, evidence, and report calculations."""
    state = load_aggregation_state()
    if state is None:
        raise DashboardNotFoundError("No completed data submission is available.")
    return DashboardContext(state=state, materialized=materialize_aggregation(state))


async def get_aggregated_dashboard(
    employee_id: str | None = None,
    team: str | None = None,
    period_weeks: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    period_preset: str | None = None,
) -> DashboardResponse:
    """Recalculate one filtered dashboard from canonical cross-submission evidence."""
    return build_dashboard(
        load_dashboard_context(), employee_id, team, period_weeks, start_date, end_date,
        period_preset
    )


def resolve_dashboard_period(
    context: DashboardContext,
    start_date: date | None,
    end_date: date | None,
    period_weeks: int | None,
    period_preset: str | None = None,
) -> tuple[date | None, date | None]:
    """Resolve periods against canonical business dates using the dashboard's rules."""
    validate_analysis_period(start_date, end_date, period_weeks, period_preset)
    overview = inspect_dataset(context.materialized.dataset)
    effective_start = start_date
    effective_end = end_date
    if period_weeks is not None and overview.date_end is not None:
        effective_end = overview.date_end
        preset_start = effective_end - timedelta(days=period_weeks * 7 - 1)
        effective_start = max(
            preset_start,
            overview.date_start or preset_start,
        )
    if period_preset is not None and overview.date_end is not None:
        effective_end = overview.date_end
        months = {"month": 1, "six-months": 6, "year": 12}[period_preset]
        effective_start = rolling_period_start(effective_end, months)
    return effective_start or overview.date_start, effective_end or overview.date_end


def build_dashboard(
    context: DashboardContext,
    employee_id: str | None = None,
    team: str | None = None,
    period_weeks: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    period_preset: str | None = None,
) -> DashboardResponse:
    """Calculate a filtered dashboard without reloading its canonical state."""
    state = context.state
    materialized = context.materialized
    dataset = materialized.dataset
    overview = inspect_dataset(dataset)
    effective_start, effective_end = resolve_dashboard_period(
        context, start_date, end_date, period_weeks, period_preset
    )
    selected_start, selected_end = effective_start, effective_end
    score_period_start: date | None = None
    score_period_end: date | None = None
    score_period_start, score_period_end = available_period_overlap(
        selected_start, selected_end, overview.date_start, overview.date_end
    )
    if score_period_start is not None and score_period_end is not None:
        effective_start, effective_end = score_period_start, score_period_end
    # Unbounded dashboard scoring retains its existing 90-day target semantics.
    if start_date is None and end_date is None and period_weeks is None and period_preset is None:
        effective_start = effective_end = None
        score_period_start = score_period_end = None

    first_summary = materialized.mapping_summaries[0]
    first_plan = CalculationPlan(
        selected_tables=first_summary.selected_tables,
        table_classifications=first_summary.table_classifications,
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
        selected_start_date=selected_start,
        selected_end_date=selected_end,
        score_period_start_date=score_period_start,
        score_period_end_date=score_period_end,
        period_weeks=period_weeks,
        period_preset=period_preset,
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
