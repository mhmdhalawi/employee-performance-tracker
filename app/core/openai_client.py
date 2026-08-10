from functools import lru_cache

from openai import AsyncOpenAI

from app.core.config import get_settings


@lru_cache
def get_openai_client() -> AsyncOpenAI | None:
    """Return a shared async client, or ``None`` if OPENAI_API_KEY is unset."""
    settings = get_settings()
    if not settings.openai_api_key:
        return None
    return AsyncOpenAI(
        api_key=settings.openai_api_key,
        timeout=settings.openai_timeout_seconds,
    )
