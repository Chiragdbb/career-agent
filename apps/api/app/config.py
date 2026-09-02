from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from packages.shared.env import project_env_file


class Settings(BaseSettings):
    """Application settings loaded from environment / `.env`."""

    model_config = SettingsConfigDict(
        env_file=project_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="career-agent-api", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
    job_scrape_freshness_days: int = Field(default=14, alias="JOB_SCRAPE_FRESHNESS_DAYS")
    skill_embed_high_threshold: float = Field(default=0.85, alias="SKILL_EMBED_HIGH_THRESHOLD")
    skill_embed_low_threshold: float = Field(default=0.7, alias="SKILL_EMBED_LOW_THRESHOLD")
    skill_possible_weight: float = Field(default=0.5, alias="SKILL_POSSIBLE_WEIGHT")

    # Comma-separated browser origins allowed to call the API (CORS).
    # Example: https://career-agent.in,https://www.career-agent.in
    cors_allow_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="CORS_ALLOW_ORIGINS",
    )

    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")

    # Supabase Auth — used for JWKS-based JWT verification (no JWT secret).
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_service_role_key: str = Field(default="", alias="SUPABASE_SERVICE_ROLE_KEY")

    # Supabase Storage — private bucket; signed URLs for client access.
    supabase_storage_bucket: str = Field(default="", alias="SUPABASE_STORAGE_BUCKET")
    supabase_storage_public_url: str = Field(default="", alias="SUPABASE_STORAGE_PUBLIC_URL")

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        # Prefer psycopg (v3) for SQLAlchemy when a bare postgresql:// URL is given.
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        return value

    @field_validator("database_url", "redis_url")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("must not be blank")
        return value.strip()

    @field_validator("supabase_url")
    @classmethod
    def normalize_supabase_url(cls, value: str) -> str:
        return (value or "").strip().rstrip("/")

    @field_validator(
        "supabase_service_role_key",
        "supabase_storage_bucket",
        "supabase_storage_public_url",
        "cors_allow_origins",
    )
    @classmethod
    def strip_optional_strings(cls, value: str) -> str:
        return (value or "").strip()

    def cors_origins_list(self) -> list[str]:
        origins = [
            origin.strip().rstrip("/")
            for origin in self.cors_allow_origins.split(",")
            if origin.strip()
        ]
        return origins or [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
