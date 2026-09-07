from datetime import date, datetime

from app.database import StoredSubmissionReceipt, load_canonical_record_types
from app.schemas.uploads import SubmissionReceipt

def _submission_receipt(stored: StoredSubmissionReceipt) -> SubmissionReceipt:
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


def _date_string(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _available_foundation_calculators() -> set[str]:
    record_types = load_canonical_record_types()
    calculators: set[str] = set()
    if "employee" in record_types:
        calculators.add("load_employees")
    if "performance_target" in record_types:
        calculators.add("load_performance_targets")
    return calculators
