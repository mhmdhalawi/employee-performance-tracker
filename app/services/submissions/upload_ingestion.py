import json
from base64 import b64encode
from datetime import date
from hashlib import sha256
from uuid import uuid4

from app.database import (
    complete_submission,
    create_submission,
    fail_submission,
    load_mapping_plan,
)
from app.schemas.performance import ValidationFinding
from app.schemas.uploads import (
    AnalysisResponse,
    AnalyzeUploadResponse,
    CalculationPlan,
    ImportIssue,
)
from app.services.agent import (
    analyze_catalog_artifacts,
    catalog_schema_fingerprint,
)
from app.services.aggregation import canonical_record_writes
from app.services.analysis import build_analysis_response
from app.services.filters import validate_analysis_period
from app.services.imports import parse_upload
from app.services.submissions.helpers import persisted_foundation_calculators
from app.utils.dates import date_string

_CANONICAL_CONFLICT_CODES = {
    "conflicting_canonical_record",
    "duplicate_canonical_record",
    "duplicate_record_content",
}


async def analyze_and_store_upload(
    file_name: str | None,
    contents: bytes,
    maximum_bytes: int,
    employee_id: str | None = None,
    team: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> AnalyzeUploadResponse:
    """Publish all uploaded evidence and return the requested analysis view."""
    source = parse_upload(file_name, contents, maximum_bytes)
    validate_analysis_period(start_date, end_date)
    submission_id = str(uuid4())
    fingerprint = catalog_schema_fingerprint(source)
    request_json = json.dumps(
        {
            "file_name": source.file_name,
            "file_type": source.file_type,
            "contents_base64": b64encode(contents).decode("ascii"),
            "catalog": source.model_dump(mode="json"),
        }
    )
    create_submission(
        submission_id=submission_id,
        request_json=request_json,
        request_sha256=sha256(request_json.encode()).hexdigest(),
        schema_fingerprint=fingerprint,
        table_count=len(source.tables),
        row_count=sum(table.row_count for table in source.tables),
    )
    try:
        plan_json = load_mapping_plan(fingerprint)
        persisted_plan = (
            CalculationPlan.model_validate_json(plan_json) if plan_json else None
        )
        header_issues = [
            ImportIssue(
                code="header_not_found",
                message="No row with at least two non-empty header values was found.",
                source_name=table.source_name,
            )
            for table in source.tables
            if table.header_row is None
        ]
        artifacts = await analyze_catalog_artifacts(
            source,
            import_issues=header_issues,
            calculation_plan=persisted_plan,
            canonicalize_batch_records=True,
            available_foundation_calculators=persisted_foundation_calculators(),
        )
        response = artifacts.response
        filtered = response
        if employee_id or team or start_date or end_date:
            filtered = build_analysis_response(
                artifacts.performance_dataset,
                artifacts.calculation_plan,
                import_issues=response.import_issues,
                employee_id=employee_id,
                team=team,
                start_date=start_date,
                end_date=end_date,
                additional_validation_findings=_canonical_conflict_findings(response),
                model=response.model,
                total_tokens=response.total_tokens,
                model_requests=response.model_requests,
                mapping_cache_hit=response.mapping_cache_hit,
            )
        complete_submission(
            submission_id=submission_id,
            schema_fingerprint=fingerprint,
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
    return AnalyzeUploadResponse(
        **filtered.model_dump(),
        file_name=source.file_name,
        file_type=source.file_type,
        byte_size=source.byte_size,
    )


def _canonical_conflict_findings(
    response: AnalysisResponse,
) -> list[ValidationFinding]:
    """Return the canonical duplicate and conflict findings a filtered view must keep."""
    findings = [
        *response.global_validation_findings,
        *(
            finding
            for result in response.results
            for finding in result.validation_findings
        ),
    ]
    return [
        finding for finding in findings if finding.code in _CANONICAL_CONFLICT_CODES
    ]
