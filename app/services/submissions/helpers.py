from datetime import date, datetime

from app.database import StoredSubmissionReceipt, load_canonical_record_types
from app.schemas.calculators import CALCULATORS, FOUNDATION_CALCULATORS
from app.schemas.uploads import SubmissionReceipt


def submission_receipt(stored: StoredSubmissionReceipt) -> SubmissionReceipt:
    """Convert a stored receipt row into the typed ingestion response."""
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


def persisted_foundation_calculators() -> set[str]:
    """Return foundation calculators already satisfied by completed canonical records."""
    record_types = load_canonical_record_types()
    return {
        spec.name
        for spec in CALCULATORS
        if spec.name in FOUNDATION_CALCULATORS and spec.record_type in record_types
    }
