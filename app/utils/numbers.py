from typing import Any

from app.schemas.kpi import MetricDirection


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    if denominator == 0:
        return default
    return numerator / denominator


def round_score(value: float) -> float:
    return round(value, 2)


def coerce_float(value: Any) -> float | None:
    """Best-effort numeric conversion that never guesses.

    Returns ``None`` for blanks and non-numeric text so the caller can report a
    data issue instead of substituting a fake zero. Handles the common
    spreadsheet decorations: thousands separators, percent signs, ``'1,5'``
    decimal commas, and ``'4h 30m'``-free plain numbers only.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        number = float(value)
        return None if number != number else number  # reject NaN

    text = str(value).strip()
    if not text or text.lower() in {"n/a", "na", "-", "--", "null", "none"}:
        return None

    is_percent = text.endswith("%")
    text = text.removesuffix("%").strip()
    text = text.replace(" ", "")
    # '1.234,56' -> '1234.56'; '1,5' -> '1.5'; '1,234' -> '1234'
    if "," in text and "." in text:
        text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", "." if len(text.rsplit(",", 1)[1]) != 3 else "")

    try:
        number = float(text)
    except ValueError:
        return None
    return number / 100 if is_percent else number


def normalize_metric(value: float, target: float, direction: MetricDirection) -> float:
    """Map a raw metric onto 0-100 relative to its target.

    ``higher_better``: ``clamp(value / target) * 100`` — hitting target scores 100,
    over-achievement is capped there (no runaway scores from one outlier metric).

    ``lower_better``: ``clamp(target / value) * 100`` — a value at or below target
    scores 100, and a value at twice the target scores 50. ``value <= 0`` scores
    100 (zero errors, zero rework).

    Kept deliberately simple and documented because it is the whole basis of every
    score the service reports.
    """
    if target <= 0:
        raise ValueError("Metric target must be positive.")

    if direction == "higher_better":
        ratio = clamp(safe_div(value, target))
    else:
        if value <= 0:
            ratio = 1.0
        else:
            ratio = clamp(safe_div(target, value))

    return round_score(ratio * 100)
