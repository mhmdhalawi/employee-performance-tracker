from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Employee Performance Tracking Agent"
    api_prefix: str = "/api/v1"
    debug: bool = Field(default=False, validation_alias="APP_DEBUG")

    cors_origins: list[str] = ["http://localhost:5173"]
    upload_max_bytes: int = 10 * 1024 * 1024
    database_path: Path = Path("storage/tracker.sqlite3")

    openai_api_key: str | None = None
    openai_model: str = "gpt-5.6-luna"

    @property
    def ai_enabled(self) -> bool:
        return bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor. Use as a FastAPI dependency or call directly."""
    return Settings()
