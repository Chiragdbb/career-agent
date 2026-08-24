from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings


def test_settings_load_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5433/career_agent")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.api_v1_prefix == "/api/v1"


def test_settings_reject_blank_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "   ")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    get_settings.cache_clear()

    with pytest.raises(ValidationError):
        Settings()


def test_settings_reject_missing_redis_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5433/db")
    monkeypatch.delenv("REDIS_URL", raising=False)
    # Ensure dotenv file values do not mask the missing env for this unit test.
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_include_optional_supabase_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5433/career_agent")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co/")
    get_settings.cache_clear()

    settings = get_settings()
    assert settings.supabase_url == "https://example.supabase.co"
