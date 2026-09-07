from hashlib import sha256
from uuid import uuid4

from app.database import (
    complete_submission,
    create_submission,
    fail_submission,
    load_mapping_plan,
    load_submission_receipt_by_idempotency_key,
)
from app.schemas.tables import AnalyzeTablesRequest
from app.schemas.uploads import CalculationPlan, SubmissionReceipt
from app.services.agent import analyze_tables_artifacts, catalog_schema_fingerprint
from app.services.aggregation import canonical_record_writes
from app.services.submissions.helpers import (
    persisted_foundation_calculators,
    submission_receipt,
)
from app.services.tables import catalog_from_tables
from app.utils.dates import date_string


async def analyze_and_store_tables(
    request: AnalyzeTablesRequest,
    idempotency_key: str | None = None,
) -> SubmissionReceipt:
    """Analyze and atomically publish one incremental JSON evidence batch."""
    if idempotency_key is not None:
        replay = load_submission_receipt_by_idempotency_key(idempotency_key)
        if replay is not None:
            return submission_receipt(replay)

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
        return submission_receipt(replay)

    persisted_plan_json = load_mapping_plan(schema_fingerprint)
    persisted_plan = (
        CalculationPlan.model_validate_json(persisted_plan_json)
        if persisted_plan_json is not None
        else None
    )
    try:
        artifacts = await analyze_tables_artifacts(
            request,
            calculation_plan=persisted_plan,
            available_foundation_calculators=persisted_foundation_calculators(),
        )
        response = artifacts.response
        receipt = complete_submission(
            submission_id=submission_id,
            schema_fingerprint=schema_fingerprint,
            calculation_plan_json=artifacts.calculation_plan.model_dump_json(),
            analysis_id=str(uuid4()),
            coverage_start=date_string(response.dataset_overview.date_start),
            coverage_end=date_string(response.dataset_overview.date_end),
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
    return submission_receipt(receipt)
