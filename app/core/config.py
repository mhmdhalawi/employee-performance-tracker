from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Employee Performance Tracking Agent"
    api_prefix: str = "/api/v1"
    debug: bool = False

    cors_origins: list[str] = ["http://localhost:5173"]
    upload_max_bytes: int = 10 * 1024 * 1024

    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"

    @property
    def ai_enabled(self) -> bool:
        return bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor. Use as a FastAPI dependency or call directly."""
    return Settings()
