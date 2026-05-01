"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed configuration sourced from environment variables / .env."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- App ----
    app_env: str = Field(default="development")
    app_secret_key: str = Field(default="change-me-in-prod")
    app_base_url: str = Field(default="http://localhost:8000")
    frontend_base_url: str = Field(default="http://localhost:3000")
    log_level: str = Field(default="INFO")

    # ---- MiMo ----
    mimo_api_key: str = Field(default="")
    mimo_base_url: str = Field(default="https://token-plan-sgp.xiaomimimo.com/v1")
    mimo_anthropic_base_url: str = Field(
        default="https://token-plan-sgp.xiaomimimo.com/anthropic"
    )
    mimo_model_pro: str = Field(default="mimo-v2.5-pro")
    mimo_model_fast: str = Field(default="mimo-v2.5")
    mimo_model_omni: str = Field(default="mimo-v2-omni")
    mimo_model_tts: str = Field(default="mimo-v2.5-tts")
    mimo_model_tts_clone: str = Field(default="mimo-v2.5-tts-voiceclone")
    mimo_model_tts_design: str = Field(default="mimo-v2.5-tts-voicedesign")

    # ---- Database ----
    database_url: str = Field(default="sqlite+aiosqlite:///./mager.db")

    # ---- Redis / queue ----
    redis_url: str = Field(default="redis://localhost:6379/0")

    # ---- Storage ----
    s3_endpoint_url: str = Field(default="http://localhost:9000")
    s3_region: str = Field(default="us-east-1")
    s3_access_key_id: str = Field(default="minioadmin")
    s3_secret_access_key: str = Field(default="minioadmin")
    s3_bucket: str = Field(default="mager-klip")
    s3_public_base_url: str = Field(default="http://localhost:9000/mager-klip")

    # ---- OAuth ----
    google_client_id: str = Field(default="")
    google_client_secret: str = Field(default="")
    youtube_client_id: str = Field(default="")
    youtube_client_secret: str = Field(default="")
    tiktok_client_key: str = Field(default="")
    tiktok_client_secret: str = Field(default="")

    # ---- Whisper ----
    whisper_model: str = Field(default="base")
    whisper_device: str = Field(default="cpu")
    whisper_compute_type: str = Field(default="int8")


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
