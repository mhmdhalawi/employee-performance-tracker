from collections.abc import Iterable


def average(values: Iterable[float]) -> float | None:
    """Return the mean rounded to two decimals, or None when nothing is available."""
    collected = list(values)
    if not collected:
        return None
    return round(sum(collected) / len(collected), 2)
