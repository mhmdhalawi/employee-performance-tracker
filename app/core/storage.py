import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast

from app.core.database import database_connection

type SubmissionStatus = Literal["pending", "completed", "failed"]


@dataclass(frozen=True, slots=True)
class CanonicalRecordWrite:
    record_type: str
    record_id: str
    employee_id: str
    period_start: str | None
    period_end: str | None
    payload_json: str
    source_version: int | None
    source_updated_at: str | None


@dataclass(frozen=True, slots=True)
class StoredCanonicalRecord:
    record_type: str
    record_id: str
    payload_json: str
    source_submission_id: str
    schema_fingerprint: str


@dataclass(frozen=True, slots=True)
class StoredSubmissionReceipt:
    submission_id: str
    status: SubmissionStatus
    received_at: str
    coverage_start: str | None
    coverage_end: str | None


@dataclass(frozen=True, slots=True)
class StoredMappingSummary:
    schema_fingerprint: str
    included_submission_count: int
    plan_json: str


@dataclass(frozen=True, slots=True)
class StoredAggregationState:
    records: list[StoredCanonicalRecord]
    mapping_summaries: list[StoredMappingSummary]
    included_submission_count: int
    latest_submission_at: str


def create_submission(
    submission_id: str,
    request_json: str,
    request_sha256: str,
    schema_fingerprint: str,
    table_count: int,
    row_count: int,
    idempotency_key: str | None = None,
) -> bool:
    """Insert a pending immutable JSON submission, returning false for a replayed key."""
    with database_connection() as connection:
        try:
            connection.execute(
                """
                INSERT INTO submissions (
                    id, received_at, status, request_sha256, schema_fingerprint,
                    table_count, row_count, request_json, idempotency_key
                ) VALUES (?, ?, 'pending', ?, ?, ?, ?, ?, ?)
                """,
                (
                    submission_id,
                    _now(),
                    request_sha256,
                    schema_fingerprint,
                    table_count,
                    row_count,
                    request_json,
                    idempotency_key,
                ),
            )
        except sqlite3.IntegrityError:
            if idempotency_key is None:
                raise
            return False
    return True


def load_submission_receipt_by_idempotency_key(
    idempotency_key: str,
) -> StoredSubmissionReceipt | None:
    """Return the original submission receipt for a deployment-wide idempotency key."""
    with database_connection() as connection:
        row = connection.execute(
            """
            SELECT s.id, s.status, s.received_at, a.coverage_start, a.coverage_end
            FROM submissions AS s
            LEFT JOIN analysis_runs AS a ON a.submission_id = s.id
            WHERE s.idempotency_key = ?
            """,
            (idempotency_key,),
        ).fetchone()
    return _receipt_from_row(row)


def load_mapping_plan(schema_fingerprint: str) -> str | None:
    """Load a validated mapping plan from the durable schema cache."""
    with database_connection() as connection:
        row = connection.execute(
            "SELECT plan_json FROM mapping_plans WHERE schema_fingerprint = ?",
            (schema_fingerprint,),
        ).fetchone()
    return row["plan_json"] if row is not None else None


def load_canonical_record_types() -> set[str]:
    """Return record types currently published by completed submissions."""
    with database_connection() as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT c.record_type
            FROM canonical_records AS c
            JOIN submissions AS s ON s.id = c.source_submission_id
            WHERE s.status = 'completed'
            """
        ).fetchall()
    return {row["record_type"] for row in rows}


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


def fail_submission(submission_id: str, error_message: str) -> None:
    """Record an analysis failure without discarding the submitted request."""
    with database_connection() as connection:
        connection.execute(
            """
            UPDATE submissions
            SET status = 'failed', completed_at = ?, error_message = ?
            WHERE id = ?
            """,
            (_now(), error_message[:1000], submission_id),
        )


def load_aggregation_state() -> StoredAggregationState | None:
    """Load canonical current state and mapping metadata from completed submissions."""
    with database_connection() as connection:
        metadata = connection.execute(
            """
            SELECT COUNT(*) AS submission_count,
                   MAX(completed_at) AS latest_submission_at
            FROM submissions AS s
            JOIN submission_plans AS sp ON sp.submission_id = s.id
            WHERE s.status = 'completed'
            """
        ).fetchone()
        if metadata is None or metadata["submission_count"] == 0:
            return None

        rows = connection.execute(
            """
            SELECT c.record_type, c.record_id, c.payload_json,
                   c.source_submission_id, s.schema_fingerprint
            FROM canonical_records AS c
            JOIN submissions AS s ON s.id = c.source_submission_id
            WHERE s.status = 'completed'
            ORDER BY c.record_type, c.record_id
            """
        ).fetchall()
        mapping_rows = connection.execute(
            """
            SELECT sp.schema_fingerprint,
                   COUNT(DISTINCT sp.submission_id) AS submission_count,
                   sp.plan_json
            FROM submission_plans AS sp
            JOIN submissions AS s ON s.id = sp.submission_id
            WHERE s.status = 'completed'
            GROUP BY sp.schema_fingerprint, sp.plan_json
            ORDER BY sp.schema_fingerprint
            """
        ).fetchall()

    return StoredAggregationState(
        records=[
            StoredCanonicalRecord(
                record_type=row["record_type"],
                record_id=row["record_id"],
                payload_json=row["payload_json"],
                source_submission_id=row["source_submission_id"],
                schema_fingerprint=row["schema_fingerprint"],
            )
            for row in rows
        ],
        mapping_summaries=[
            StoredMappingSummary(
                schema_fingerprint=row["schema_fingerprint"],
                included_submission_count=row["submission_count"],
                plan_json=row["plan_json"],
            )
            for row in mapping_rows
        ],
        included_submission_count=metadata["submission_count"],
        latest_submission_at=metadata["latest_submission_at"],
    )


def _receipt_from_row(row: sqlite3.Row | None) -> StoredSubmissionReceipt | None:
    if row is None:
        return None
    return StoredSubmissionReceipt(
        submission_id=row["id"],
        status=_submission_status(row["status"]),
        received_at=row["received_at"],
        coverage_start=row["coverage_start"],
        coverage_end=row["coverage_end"],
    )


def _submission_status(value: str) -> SubmissionStatus:
    if value not in {"pending", "completed", "failed"}:
        raise RuntimeError(f"Unexpected persisted submission status: {value!r}.")
    return cast(SubmissionStatus, value)


def _now() -> str:
    return datetime.now(UTC).isoformat()
