"""Domain tests for scheduled discovery fan-out (mocked session)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from packages.domain.scheduled_discovery import run_scheduled_discover_for_active_users


class RecordingTaskClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def enqueue_discover_jobs(self, **kw):
        self.calls.append(kw)
        return "t1"

    def enqueue_rescrape_job(self, **kw):
        raise AssertionError("not used")


def test_skips_disabled_schedule():
    user_id = uuid.uuid4()
    user = SimpleNamespace(id=user_id)
    prefs = SimpleNamespace(settings={"discovery_schedule": {"enabled": False}})

    session = MagicMock()
    user_q = MagicMock()
    user_q.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [user]
    prefs_q = MagicMock()
    prefs_q.filter.return_value.one_or_none.return_value = prefs

    def _query(model):
        from database.models.schema import User, UserPreference

        if model is User:
            return user_q
        if model is UserPreference:
            return prefs_q
        raise AssertionError(f"unexpected model {model}")

    session.query.side_effect = _query
    client = RecordingTaskClient()

    out = run_scheduled_discover_for_active_users(session, client, max_users=10)

    assert out["enqueued"] == []
    assert any(s["reason"] == "disabled" and s["user_id"] == str(user_id) for s in out["skipped"])
    assert client.calls == []


def test_enqueues_enabled_user():
    user_id = uuid.uuid4()
    run_id = uuid.uuid4()
    user = SimpleNamespace(id=user_id)
    prefs = SimpleNamespace(settings={"discovery_schedule": {"enabled": True}})

    session = MagicMock()
    user_q = MagicMock()
    user_q.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [user]
    prefs_q = MagicMock()
    prefs_q.filter.return_value.one_or_none.return_value = prefs

    def _query(model):
        from database.models.schema import User, UserPreference

        if model is User:
            return user_q
        if model is UserPreference:
            return prefs_q
        raise AssertionError(f"unexpected model {model}")

    session.query.side_effect = _query

    usage = MagicMock()
    trigger = MagicMock()
    trigger.enqueue.return_value = SimpleNamespace(workflow_run_id=run_id)
    client = RecordingTaskClient()

    with (
        patch(
            "packages.domain.scheduled_discovery.ProviderUsageService",
            return_value=usage,
        ),
        patch(
            "packages.domain.scheduled_discovery.DiscoveryTriggerService",
            return_value=trigger,
        ),
    ):
        out = run_scheduled_discover_for_active_users(session, client, max_users=10)

    assert out["enqueued"] == [str(run_id)]
    assert client.calls == [
        {"user_id": user_id, "workflow_run_id": run_id, "max_results": 20}
    ]
    trigger.attach_task_id.assert_called_once_with(run_id, "t1")
    usage.check_quota.assert_called_once()
