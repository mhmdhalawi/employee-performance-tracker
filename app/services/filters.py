from calendar import monthrange
from datetime import date, timedelta

from app.core.errors import InvalidAnalysisFilterError

ALLOWED_PERIOD_WEEKS = (4, 8, 12)
ALLOWED_PERIOD_PRESETS = ("month", "six-months", "year")


def validate_analysis_period(
    start_date: date | None,
    end_date: date | None,
    period_weeks: int | None = None,
    period_preset: str | None = None,
) -> None:
    """Reject reporting-period filters that cannot be resolved deterministically."""
    if period_weeks is not None and (start_date is not None or end_date is not None):
        raise InvalidAnalysisFilterError(
            "period_weeks cannot be combined with start_date or end_date."
        )
    if period_weeks is not None and period_weeks not in ALLOWED_PERIOD_WEEKS:
        raise InvalidAnalysisFilterError("period_weeks must be 4, 8, or 12.")
    if period_preset is not None:
        if period_preset not in ALLOWED_PERIOD_PRESETS:
            raise InvalidAnalysisFilterError(
                "period_preset must be month, six-months, or year."
            )
        if period_weeks is not None or start_date is not None or end_date is not None:
            raise InvalidAnalysisFilterError(
                "period_preset cannot be combined with period_weeks, start_date, or end_date."
            )
    if start_date is not None and end_date is not None and start_date > end_date:
        raise InvalidAnalysisFilterError("start_date must be on or before end_date.")


def rolling_period_start(end_date: date, months: int) -> date:
    """Return an inclusive rolling calendar-month start for a canonical business date."""
    previous_month = end_date.month - months
    year = end_date.year + (previous_month - 1) // 12
    if year < 1:
        return date.min
    month = (previous_month - 1) % 12 + 1
    prior_day = min(end_date.day, monthrange(year, month)[1])
    return date(year, month, prior_day) + timedelta(days=1)


def available_period_overlap(
    selected_start: date | None,
    selected_end: date | None,
    coverage_start: date | None,
    coverage_end: date | None,
) -> tuple[date | None, date | None]:
    """Return the date window where selected dates and canonical coverage overlap."""
    if (
        selected_start is None
        or selected_end is None
        or coverage_start is None
        or coverage_end is None
    ):
        return None, None
    overlap_start = max(selected_start, coverage_start)
    overlap_end = min(selected_end, coverage_end)
    return (overlap_start, overlap_end) if overlap_start <= overlap_end else (None, None)
