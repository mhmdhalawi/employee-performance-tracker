from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.database import database_connection


@dataclass(frozen=True, slots=True)
class StoredDashboard:
    request_json: str
    response_json: str
    calculation_plan_json: str


def create_submission(
    submission_id: str,
    request_json: str,
    request_sha256: str,
    schema_fingerprint: str,
    table_count: int,
    row_count: int,
) -> None:
    """Insert a pending immutable JSON submission before analysis starts."""
    with database_connection() as connection:
        connection.execute(
            """
            INSERT INTO submissions (
                id, received_at, status, request_sha256, schema_fingerprint,
                table_count, row_count, request_json
            ) VALUES (?, ?, 'pending', ?, ?, ?, ?, ?)
            """,
            (
                submission_id,
                _now(),
                request_sha256,
                schema_fingerprint,
                table_count,
                row_count,
                request_json,
            ),
        )


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
) -> None:
    """Atomically save the mapping plan, dashboard snapshot, and completion state."""
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
            (
                schema_fingerprint,
                completed_at,
                completed_at,
                calculation_plan_json,
            ),
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
        connection.execute(
            """
            UPDATE submissions
            SET status = 'completed', completed_at = ?, error_message = NULL
            WHERE id = ?
            """,
            (completed_at, submission_id),
        )


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


def load_latest_dashboard() -> StoredDashboard | None:
    """Load the newest successfully completed canonical dashboard and its source request."""
    with database_connection() as connection:
        row = connection.execute(
            """
            SELECT s.request_json, a.response_json, m.plan_json
            FROM analysis_runs AS a
            JOIN submissions AS s ON s.id = a.submission_id
            JOIN mapping_plans AS m ON m.schema_fingerprint = s.schema_fingerprint
            WHERE s.status = 'completed'
            ORDER BY a.created_at DESC, a.rowid DESC
            LIMIT 1
            """
        ).fetchone()
    if row is None:
        return None
    return StoredDashboard(
        request_json=row["request_json"],
        response_json=row["response_json"],
        calculation_plan_json=row["plan_json"],
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()
