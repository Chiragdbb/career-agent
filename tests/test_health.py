from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


def test_liveness_endpoint_ok() -> None:
    settings = get_settings()
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == settings.app_name
    assert "checks" not in body


def test_root_liveness_for_render_probe() -> None:
    settings = get_settings()
    app = create_app(settings)

    with TestClient(app) as client:
        head = client.head("/")
        get = client.get("/")

    assert head.status_code == 200
    assert get.status_code == 200
    assert get.json()["status"] == "ok"
    assert get.json()["service"] == settings.app_name


def test_health_endpoint_ok() -> None:
    settings = get_settings()
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["redis"] == "ok"
    assert "X-Correlation-ID" in response.headers
    assert body["correlation_id"] == response.headers["X-Correlation-ID"]


def test_health_endpoint_uses_incoming_correlation_id() -> None:
    settings = get_settings()
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/health",
            headers={"X-Correlation-ID": "test-corr-123"},
        )

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "test-corr-123"
    assert response.json()["correlation_id"] == "test-corr-123"
