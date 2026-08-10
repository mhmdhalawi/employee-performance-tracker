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

    # Vue dev server by default.
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Upload guards, checked before the file is handed to pandas.
    max_upload_bytes: int = 10 * 1024 * 1024
    allowed_upload_extensions: list[str] = [".csv", ".xlsx", ".xls"]

    # AI report generation. Without a key the service falls back to a
    # deterministic template summary instead of failing.
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_timeout_seconds: float = 30.0
    openai_max_output_tokens: int = 900

    # Kill switch for the AI column-mapping agent. When off, hybrid/ai upload modes
    # degrade to deterministic alias matching.
    ai_mapping_enabled: bool = True
    # Mappings below this confidence are still applied, but flagged in the response.
    ai_mapping_low_confidence: float = 0.6

    @property
    def ai_enabled(self) -> bool:
        return bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor. Use as a FastAPI dependency or call directly."""
    return Settings()
