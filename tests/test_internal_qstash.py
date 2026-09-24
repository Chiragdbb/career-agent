"""API tests for /internal/qstash callback routes."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from packages.domain.exceptions import DiscoveryCancelledError, DomainError

from app.config import get_settings
from app.database import get_db
from app.main import create_app
from app.redis import get_redis
from app.tasks import InlineDiscoveryTaskClient


class FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def set(self, name: str, value: str, nx: bool = False, ex: int | None = None) -> bool:
        if nx and name in self._store:
            return False
        self._store[name] = value
        return True

    def get(self, name: str) -> str | None:
        return self._store.get(name)

    def delete(self, name: str) -> int:
        if name in self._store:
            del self._store[name]
            return 1
        return 0

    def setex(self, name: str, time: int, value: str) -> None:
        self._store[name] = value

    def publish(self, channel: str, message: str) -> int:
        return 0

    def close(self) -> None:
        pass

    def pubsub(self, **kwargs):
        class _PubSub:
            def subscribe(self, *args, **kwargs): ...
            def listen(self):
                return iter(())

            def unsubscribe(self, *args, **kwargs): ...
            def close(self): ...

        return _PubSub()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QSTASH_CURRENT_SIGNING_KEY", "test-signing-key")
    monkeypatch.setenv("QSTASH_NEXT_SIGNING_KEY", "")
    get_settings.cache_clear()

    settings = get_settings()
    app = create_app(settings)
    app.state.discovery_task_client = InlineDiscoveryTaskClient()
    fake_redis = FakeRedis()
    fake_session = MagicMock(name="db_session")
    app.dependency_overrides[get_redis] = lambda: fake_redis
    app.dependency_overrides[get_db] = lambda: fake_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_discover_jobs_rejects_bad_signature(client):
    r = client.post(
        "/internal/qstash/discover-jobs",
        json={
            "user_id": str(uuid.uuid4()),
            "workflow_run_id": str(uuid.uuid4()),
            "max_results": 1,
        },
        headers={"Upstash-Signature": "bad"},
    )
    assert r.status_code in (401, 403)


def test_discover_jobs_runs_when_verified(client, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "app.routers.internal_qstash.verify_upstash_signature",
        lambda **kw: True,
    )
    called: dict = {}

    def fake_run(uid, rid, mx):
        called["ok"] = True
        called["args"] = (uid, rid, mx)
        return {"status": "ok"}

    monkeypatch.setattr(
        "app.routers.internal_qstash._run_discovery",
        fake_run,
    )
    user_id = uuid.uuid4()
    run_id = uuid.uuid4()
    r = client.post(
        "/internal/qstash/discover-jobs",
        json={
            "user_id": str(user_id),
            "workflow_run_id": str(run_id),
            "max_results": 3,
        },
        headers={"Upstash-Signature": "ok"},
    )
    assert r.status_code == 200
    assert called["ok"] is True
    assert called["args"] == (user_id, run_id, 3)
    body = r.json()
    assert body["ok"] is True
    assert body["result"] == {"status": "ok"}


def test_discover_jobs_domain_error_returns_200_skipped(
    client, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "app.routers.internal_qstash.verify_upstash_signature",
        lambda **kw: True,
    )

    def fake_run(*_args, **_kwargs):
        raise DiscoveryCancelledError("discovery lock held")

    monkeypatch.setattr(
        "app.routers.internal_qstash._run_discovery",
        fake_run,
    )
    r = client.post(
        "/internal/qstash/discover-jobs",
        json={
            "user_id": str(uuid.uuid4()),
            "workflow_run_id": str(uuid.uuid4()),
            "max_results": 1,
        },
        headers={"Upstash-Signature": "ok"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body == {
        "ok": True,
        "skipped": True,
        "reason": "discovery lock held",
    }


def test_rescrape_job_domain_error_returns_200_skipped(
    client, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "app.routers.internal_qstash.verify_upstash_signature",
        lambda **kw: True,
    )

    def fake_run(*_args, **_kwargs):
        raise DomainError("Job has no source URL to re-scrape")

    monkeypatch.setattr(
        "app.routers.internal_qstash._run_rescrape",
        fake_run,
    )
    r = client.post(
        "/internal/qstash/rescrape-job",
        json={
            "user_id": str(uuid.uuid4()),
            "workflow_run_id": str(uuid.uuid4()),
            "match_id": str(uuid.uuid4()),
        },
        headers={"Upstash-Signature": "ok"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["skipped"] is True
    assert "no source URL" in body["reason"]


def test_rescrape_job_runs_when_verified(client, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "app.routers.internal_qstash.verify_upstash_signature",
        lambda **kw: True,
    )
    called: dict = {}

    def fake_run(uid, rid, mid):
        called["ok"] = True
        called["args"] = (uid, rid, mid)
        return {"status": "rescraped"}

    monkeypatch.setattr(
        "app.routers.internal_qstash._run_rescrape",
        fake_run,
    )
    user_id = uuid.uuid4()
    run_id = uuid.uuid4()
    match_id = uuid.uuid4()
    r = client.post(
        "/internal/qstash/rescrape-job",
        json={
            "user_id": str(user_id),
            "workflow_run_id": str(run_id),
            "match_id": str(match_id),
        },
        headers={"Upstash-Signature": "ok"},
    )
    assert r.status_code == 200
    assert called["ok"] is True
    assert called["args"] == (user_id, run_id, match_id)
    assert r.json()["ok"] is True


def test_scheduled_discover_runs_when_verified(client, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "app.routers.internal_qstash.verify_upstash_signature",
        lambda **kw: True,
    )
    called: dict = {}

    def fake_scheduled(session, task_client, *, max_users: int = 50):
        called["ok"] = True
        called["max_users"] = max_users
        return {"enqueued": [], "skipped": [{"reason": "disabled"}], "at": "now"}

    monkeypatch.setattr(
        "app.routers.internal_qstash.run_scheduled_discover_for_active_users",
        fake_scheduled,
    )
    r = client.post(
        "/internal/qstash/scheduled-discover",
        json={},
        headers={"Upstash-Signature": "ok"},
    )
    assert r.status_code == 200
    assert called["ok"] is True
    body = r.json()
    assert body["ok"] is True
    assert body["result"]["skipped"][0]["reason"] == "disabled"


def test_verify_url_uses_callback_base_when_set():
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app.routers.internal_qstash import _verify_url

    settings = SimpleNamespace(qstash_callback_base_url="https://api.example.com/")
    request = MagicMock()
    request.url.path = "/internal/qstash/discover-jobs"
    assert (
        _verify_url(request, settings)
        == "https://api.example.com/internal/qstash/discover-jobs"
    )


def test_verify_url_falls_back_to_request_url_when_base_unset():
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app.routers.internal_qstash import _verify_url

    settings = SimpleNamespace(qstash_callback_base_url="")
    request = MagicMock()
    request.url = "https://proxy.internal/internal/qstash/discover-jobs"
    assert _verify_url(request, settings) == str(request.url)


def test_discover_jobs_401_logs_verify_url(client, monkeypatch: pytest.MonkeyPatch, caplog):
    import logging

    monkeypatch.setenv("QSTASH_CALLBACK_BASE_URL", "https://api.example.com")
    get_settings.cache_clear()

    with caplog.at_level(logging.WARNING, logger="app.routers.internal_qstash"):
        r = client.post(
            "/internal/qstash/discover-jobs",
            json={
                "user_id": str(uuid.uuid4()),
                "workflow_run_id": str(uuid.uuid4()),
                "max_results": 1,
            },
            headers={"Upstash-Signature": "bad"},
        )
    assert r.status_code in (401, 403)
    assert any(
        "qstash_signature_rejected" in rec.message
        and "https://api.example.com/internal/qstash/discover-jobs" in rec.message
        for rec in caplog.records
    )
    get_settings.cache_clear()
