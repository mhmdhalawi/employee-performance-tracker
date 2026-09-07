from app.database.connection import database_connection


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

