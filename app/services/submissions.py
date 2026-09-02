from datetime import date
from hashlib import sha256
import json
from uuid import uuid4

from app.core.errors import DashboardNotFoundError
from app.core.storage import (
    complete_submission,
    create_submission,
    fail_submission,
    load_latest_dashboard,
)
from app.schemas.tables import AnalyzeTablesRequest
from app.schemas.uploads import AnalysisResponse, CalculationPlan
from app.services.agent import (
    analyze_tables,
    refresh_analysis_insight_context,
)


async def analyze_and_store_tables(
    request: AnalyzeTablesRequest,
    employee_id: str | None = None,
    team: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> AnalysisResponse:
    """Analyze canonical webhook tables and durably store the request and response."""
    if any(value is not None for value in (employee_id, team, start_date, end_date)):
        return await analyze_tables(
            request,
            employee_id=employee_id,
            team=team,
            start_date=start_date,
            end_date=end_date,
        )

    request_json = request.model_dump_json()
    schema_fingerprint = _schema_fingerprint(request)
    submission_id = str(uuid4())
    create_submission(
        submission_id=submission_id,
        request_json=request_json,
        request_sha256=sha256(request_json.encode()).hexdigest(),
        schema_fingerprint=schema_fingerprint,
        table_count=len(request.tables),
        row_count=sum(len(table.rows) for table in request.tables),
    )
    try:
        response = await analyze_tables(request)
        calculation_plan = CalculationPlan(
            selected_tables=response.selected_tables,
            table_classifications=response.table_classifications,
        )
        complete_submission(
            submission_id=submission_id,
            schema_fingerprint=schema_fingerprint,
            calculation_plan_json=calculation_plan.model_dump_json(),
            analysis_id=response.analysis_id,
            coverage_start=_date_string(response.dataset_overview.date_start),
            coverage_end=_date_string(response.dataset_overview.date_end),
            model=response.model,
            total_tokens=response.total_tokens,
            model_requests=response.model_requests,
            mapping_cache_hit=response.mapping_cache_hit,
            response_json=response.model_dump_json(),
        )
    except Exception as exc:
        fail_submission(submission_id, str(exc))
        raise
    return response


async def get_latest_dashboard(
    employee_id: str | None = None,
    team: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> AnalysisResponse:
    """Return the latest snapshot or deterministically recalculate a filtered view."""
    stored = load_latest_dashboard()
    if stored is None:
        raise DashboardNotFoundError(
            "No completed data submission is available. Send tables to /api/v1/analyze-tables first."
        )

    if not any(value is not None for value in (employee_id, team, start_date, end_date)):
        response = AnalysisResponse.model_validate_json(stored.response_json)
        return refresh_analysis_insight_context(response)

    request = AnalyzeTablesRequest.model_validate_json(stored.request_json)
    calculation_plan = CalculationPlan.model_validate_json(
        stored.calculation_plan_json
    )
    return await analyze_tables(
        request,
        employee_id=employee_id,
        team=team,
        start_date=start_date,
        end_date=end_date,
        calculation_plan=calculation_plan,
    )


def _schema_fingerprint(request: AnalyzeTablesRequest) -> str:
    schema = {
        "tables": [
            {
                "source_name": table.source_name,
                "columns": sorted({column for row in table.rows for column in row}),
                "column_types": {
                    column: sorted(
                        {
                            type(row.get(column)).__name__
                            for row in table.rows
                            if row.get(column) is not None
                        }
                    )
                    for column in sorted({column for row in table.rows for column in row})
                },
            }
            for table in request.tables
        ]
    }
    encoded = json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()


def _date_string(value: date | None) -> str | None:
    return value.isoformat() if value else None
