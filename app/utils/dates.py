from datetime import date, datetime


def date_string(value: date | None) -> str | None:
    """Serialize an optional date for SQLite storage."""
    return value.isoformat() if value is not None else None


def datetime_string(value: datetime | None) -> str | None:
    """Serialize an optional timestamp for SQLite storage."""
    return value.isoformat() if value is not None else None
