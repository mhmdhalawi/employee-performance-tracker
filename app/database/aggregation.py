from app.database.connection import database_connection
from app.database.models import (
    StoredAggregationState,
    StoredCanonicalRecord,
    StoredMappingSummary,
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

