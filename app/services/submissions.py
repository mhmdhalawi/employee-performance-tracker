from datetime import date, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from app.core.errors import DashboardNotFoundError, InvalidAnalysisFilterError
from app.core.storage import (
    StoredSubmissionReceipt,
    complete_submission,
    create_submission,
    fail_submission,
    load_aggregation_state,
    load_canonical_record_types,
    load_mapping_plan,
    load_submission_receipt_by_idempotency_key,
)
from app.schemas.tables import AnalyzeTablesRequest
from app.schemas.uploads import (
    CalculationPlan,
    DashboardResponse,
    EmployeeFilterOption,
    SubmissionReceipt,
)
from app.services.agent import (
    analyze_tables_artifacts,
    build_analysis_response,
    catalog_schema_fingerprint,
)
from app.services.aggregation import (
    canonical_record_writes,
    materialize_aggregation,
)
from app.services.performance import inspect_dataset
from app.services.tables import catalog_from_tables


async def analyze_and_store_tables(
    request: AnalyzeTablesRequest,
    idempotency_key: str | None = None,
) -> SubmissionReceipt:
    """Analyze and atomically publish one incremental JSON evidence batch."""
    if idempotency_key is not None:
        replay = load_submission_receipt_by_idempotency_key(idempotency_key)
        if replay is not None:
            return _submission_receipt(replay)

    request_json = request.model_dump_json()
    schema_fingerprint = catalog_schema_fingerprint(catalog_from_tables(request))
    submission_id = str(uuid4())
    created = create_submission(
        submission_id=submission_id,
        request_json=request_json,
        request_sha256=sha256(request_json.encode()).hexdigest(),
        schema_fingerprint=schema_fingerprint,
        table_count=len(request.tables),
        row_count=sum(len(table.rows) for table in request.tables),
        idempotency_key=idempotency_key,
    )
    if not created:
        replay = (
            load_submission_receipt_by_idempotency_key(idempotency_key)
            if idempotency_key is not None
            else None
        )
        if replay is None:
            raise RuntimeError("The idempotent submission could not be reloaded.")
        return _submission_receipt(replay)

    persisted_plan_json = load_mapping_plan(schema_fingerprint)
    persisted_plan = (
        CalculationPlan.model_validate_json(persisted_plan_json)
        if persisted_plan_json is not None
        else None
    )
    try:
        available_foundations = _available_foundation_calculators()
        artifacts = await analyze_tables_artifacts(
            request,
            calculation_plan=persisted_plan,
            available_foundation_calculators=available_foundations,
        )
        response = artifacts.response
        receipt = complete_submission(
            submission_id=submission_id,
            schema_fingerprint=schema_fingerprint,
            calculation_plan_json=artifacts.calculation_plan.model_dump_json(),
            analysis_id=response.analysis_id,
            coverage_start=_date_string(response.dataset_overview.date_start),
            coverage_end=_date_string(response.dataset_overview.date_end),
            model=response.model,
            total_tokens=response.total_tokens,
            model_requests=response.model_requests,
            mapping_cache_hit=response.mapping_cache_hit,
            response_json=response.model_dump_json(),
            canonical_records=canonical_record_writes(artifacts.performance_dataset),
        )
    except Exception as exc:
        fail_submission(submission_id, str(exc))
        raise
    return _submission_receipt(receipt)


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
    if period_weeks is not None and period_weeks not in {4, 8, 12}:
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
        analysis_id=response.analysis_id,
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


def _submission_receipt(stored: StoredSubmissionReceipt) -> SubmissionReceipt:
    return SubmissionReceipt(
        submission_id=stored.submission_id,
        status=stored.status,
        received_at=datetime.fromisoformat(stored.received_at),
        coverage_start=date.fromisoformat(stored.coverage_start)
        if stored.coverage_start
        else None,
        coverage_end=date.fromisoformat(stored.coverage_end)
        if stored.coverage_end
        else None,
    )


def _date_string(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _available_foundation_calculators() -> set[str]:
    record_types = load_canonical_record_types()
    calculators: set[str] = set()
    if "employee" in record_types:
        calculators.add("load_employees")
    if "performance_target" in record_types:
        calculators.add("load_performance_targets")
    return calculators
