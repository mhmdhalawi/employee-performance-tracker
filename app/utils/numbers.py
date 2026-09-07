from collections.abc import Iterable


def average(values: Iterable[float]) -> float | None:
    """Return the mean rounded to two decimals, or None when nothing is available."""
    available = list(values)
    return round(sum(available) / len(available), 2) if available else None
