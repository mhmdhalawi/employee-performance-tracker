from urllib.parse import urlparse


def is_safe_evidence_link(value: str | None) -> bool:
    """Allow only absolute HTTPS evidence links."""
    if not value:
        return False
    try:
        parsed = urlparse(value)
        return parsed.scheme == "https" and bool(parsed.hostname)
    except ValueError:
        return False
