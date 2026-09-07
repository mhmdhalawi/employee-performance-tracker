from datetime import date

from app.core.errors import InvalidAnalysisFilterError

ALLOWED_PERIOD_WEEKS = (4, 8, 12)


def validate_analysis_period(
    start_date: date | None,
    end_date: date | None,
    period_weeks: int | None = None,
) -> None:
    """Reject reporting-period filters that cannot be resolved deterministically."""
    if period_weeks is not None and (start_date is not None or end_date is not None):
        raise InvalidAnalysisFilterError(
            "period_weeks cannot be combined with start_date or end_date."
        )
    if period_weeks is not None and period_weeks not in ALLOWED_PERIOD_WEEKS:
        raise InvalidAnalysisFilterError("period_weeks must be 4, 8, or 12.")
    if start_date is not None and end_date is not None and start_date > end_date:
        raise InvalidAnalysisFilterError("start_date must be on or before end_date.")
