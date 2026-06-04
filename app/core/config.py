"""Application settings, loaded from environment variables / .env file."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration for the InterviewFindr service.

    Values come from environment variables (or a local .env file).
    The application refuses to start if APP_SECRET_KEY is missing
    or shorter than 32 characters.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    app_secret_key: str = Field(min_length=32)
    database_url: str

    minio_endpoint: str = "minio:9000"
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str = "interviewfindr"
    minio_secure: bool = False

    opencode_zen_api_key: str
    opencode_zen_base_url: str = "https://opencode.ai/zen/go/v1"

    session_cookie_name: str = "if_session"
    session_ttl_days: int = 30

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide Settings singleton.

    Cached so tests can monkeypatch the environment before the first
    call and still see consistent values.
    """
    return Settings()
