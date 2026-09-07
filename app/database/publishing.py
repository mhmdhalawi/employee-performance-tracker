from app.database.connection import database_connection
from app.database.models import CanonicalRecordWrite, StoredSubmissionReceipt
from app.database.submissions import _now, _receipt_from_row


def complete_submission(
    submission_id: str,
    schema_fingerprint: str,
    calculation_plan_json: str,
    analysis_id: str,
    coverage_start: str | None,
    coverage_end: str | None,
    model: str,
    total_tokens: int,
    model_requests: int,
    mapping_cache_hit: bool,
    response_json: str,
    canonical_records: list[CanonicalRecordWrite],
) -> StoredSubmissionReceipt:
    """Atomically publish canonical rows, audit artifacts, and completion state."""
    completed_at = _now()
    with database_connection() as connection:
        connection.execute(
            """
            INSERT INTO mapping_plans (
                schema_fingerprint, created_at, updated_at, plan_json
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(schema_fingerprint) DO UPDATE SET
                updated_at = excluded.updated_at,
                plan_json = excluded.plan_json
            """,
            (schema_fingerprint, completed_at, completed_at, calculation_plan_json),
        )
        connection.execute(
            """
            INSERT INTO submission_plans (
                submission_id, schema_fingerprint, plan_json, created_at
            ) VALUES (?, ?, ?, ?)
            """,
            (submission_id, schema_fingerprint, calculation_plan_json, completed_at),
        )
        connection.execute(
            """
            INSERT INTO analysis_runs (
                analysis_id, submission_id, created_at, coverage_start, coverage_end,
                model, total_tokens, model_requests, mapping_cache_hit, response_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                analysis_id,
                submission_id,
                completed_at,
                coverage_start,
                coverage_end,
                model,
                total_tokens,
                model_requests,
                int(mapping_cache_hit),
                response_json,
            ),
        )
        for record in canonical_records:
            connection.execute(
                """
                INSERT INTO canonical_records (
                    record_type, record_id, employee_id, period_start, period_end,
                    payload_json, source_version, source_updated_at,
                    source_submission_id, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(record_type, record_id) DO UPDATE SET
                    employee_id = excluded.employee_id,
                    period_start = excluded.period_start,
                    period_end = excluded.period_end,
                    payload_json = excluded.payload_json,
                    source_version = excluded.source_version,
                    source_updated_at = excluded.source_updated_at,
                    source_submission_id = excluded.source_submission_id,
                    updated_at = excluded.updated_at
                WHERE
                    (
                        excluded.source_version IS NOT NULL
                        AND (
                            canonical_records.source_version IS NULL
                            OR excluded.source_version > canonical_records.source_version
                            OR (
                                excluded.source_version = canonical_records.source_version
                                AND excluded.source_updated_at IS NOT NULL
                                AND (
                                    canonical_records.source_updated_at IS NULL
                                    OR excluded.source_updated_at > canonical_records.source_updated_at
                                )
                            )
                        )
                    )
                    OR (
                        excluded.source_version IS NULL
                        AND canonical_records.source_version IS NULL
                        AND (
                            (
                                excluded.source_updated_at IS NOT NULL
                                AND (
                                    canonical_records.source_updated_at IS NULL
                                    OR excluded.source_updated_at > canonical_records.source_updated_at
                                )
                            )
                            OR (
                                excluded.source_updated_at IS NULL
                                AND canonical_records.source_updated_at IS NULL
                                AND excluded.updated_at > canonical_records.updated_at
                            )
                        )
                    )
                """,
                (
                    record.record_type,
                    record.record_id,
                    record.employee_id,
                    record.period_start,
                    record.period_end,
                    record.payload_json,
                    record.source_version,
                    record.source_updated_at,
                    submission_id,
                    completed_at,
                ),
            )
        connection.execute(
            """
            UPDATE submissions
            SET status = 'completed', completed_at = ?, error_message = NULL
            WHERE id = ?
            """,
            (completed_at, submission_id),
        )
        row = connection.execute(
            """
            SELECT s.id, s.status, s.received_at, a.coverage_start, a.coverage_end
            FROM submissions AS s
            JOIN analysis_runs AS a ON a.submission_id = s.id
            WHERE s.id = ?
            """,
            (submission_id,),
        ).fetchone()
    receipt = _receipt_from_row(row)
    if receipt is None:
        raise RuntimeError("Completed submission receipt was not found.")
    return receipt

