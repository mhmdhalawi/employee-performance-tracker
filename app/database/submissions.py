import sqlite3
from datetime import UTC, datetime
from typing import cast

from app.database.connection import database_connection
from app.database.models import StoredSubmissionReceipt, SubmissionStatus


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
                    now_timestamp(),
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
    return receipt_from_row(row)


def fail_submission(submission_id: str, error_message: str) -> None:
    """Record an analysis failure without discarding the submitted request."""
    with database_connection() as connection:
        connection.execute(
            """
            UPDATE submissions
            SET status = 'failed', completed_at = ?, error_message = ?
            WHERE id = ?
            """,
            (now_timestamp(), error_message[:1000], submission_id),
        )


def receipt_from_row(row: sqlite3.Row | None) -> StoredSubmissionReceipt | None:
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


def now_timestamp() -> str:
    return datetime.now(UTC).isoformat()

