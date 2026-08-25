from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_cors_origins_list_parses_comma_separated_values() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://career:career@localhost:5433/career_agent",
        REDIS_URL="redis://localhost:6379/0",
        CORS_ALLOW_ORIGINS="https://career-agent.in, https://www.career-agent.in/",
    )
    assert settings.cors_origins_list() == [
        "https://career-agent.in",
        "https://www.career-agent.in",
    ]


def test_cors_preflight_allows_configured_origin(monkeypatch) -> None:
    monkeypatch.setenv(
        "CORS_ALLOW_ORIGINS",
        "https://career-agent.in,http://localhost:3000",
    )
    from app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.options(
            "/api/v1/me",
            headers={
                "Origin": "https://career-agent.in",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://career-agent.in"
