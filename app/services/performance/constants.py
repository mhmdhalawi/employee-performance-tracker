REQUIRED_EVIDENCE_MATRIX: dict[str, tuple[str, ...]] = {
    "productivity": (
        "verified completion status",
        "actual effort hours for completed work",
    ),
    "compliance": (
        "scheduled and actual arrival when mapped",
        "scheduled and actual shift end when mapped",
        "lunch check-out and return when mapped",
        "submitted date and verified report evidence",
        "complete approved sick-leave documentation",
    ),
    "quality": (
        "verified accuracy",
        "first-pass result",
        "rework hours",
    ),
}

_NEUTRAL_ATTENDANCE_OUTCOMES = {
    "annual leave",
    "sick leave",
    "holiday",
    "public holiday",
}

