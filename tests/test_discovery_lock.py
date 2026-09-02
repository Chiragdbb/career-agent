"""Tests for per-user discovery lock."""

from __future__ import annotations

import uuid

import pytest

from database.models.enums import UserStatus, WorkflowRunStatus
from database.models.schema import User, WorkflowRun
from packages.domain.discovery_lock import DiscoveryLock
from packages.domain.exceptions import ConflictError
from packages.domain.jobs import DiscoveryTriggerService


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


def _session():
    from app.database import get_session_factory

    return get_session_factory()()


@pytest.fixture
def lock_user():
    session = _session()
    user = User(id=uuid.uuid4(), auth_subject=f"lock-{uuid.uuid4()}", status=UserStatus.active)
    session.add(user)
    session.commit()
    try:
        yield session, user, FakeRedis()
    finally:
        session.query(WorkflowRun).filter(WorkflowRun.user_id == user.id).delete()
        session.query(User).filter(User.id == user.id).delete()
        session.commit()
        session.close()


def test_second_enqueue_raises_conflict(lock_user) -> None:
    session, user, redis = lock_user
    lock = DiscoveryLock(redis)
    trigger = DiscoveryTriggerService(session, user.id, discovery_lock=lock)
    first = trigger.enqueue(max_results=3)
    with pytest.raises(ConflictError) as exc:
        trigger.enqueue(max_results=3)
    assert exc.value.details.get("workflow_run_id") == str(first.workflow_run_id)
    runs = (
        session.query(WorkflowRun)
        .filter(WorkflowRun.user_id == user.id, WorkflowRun.workflow_type == "job_discovery")
        .all()
    )
    assert len(runs) == 1


def test_lock_released_after_discovery(lock_user) -> None:
    from packages.domain.job_discovery import JobDiscoveryService
    from packages.domain.preferences import PreferenceSettings
    from packages.providers.llm import MockLLMProvider
    from packages.providers.scraper import MockScraperProvider
    from packages.providers.search import MockSearchProvider

    session, user, redis = lock_user
    lock = DiscoveryLock(redis)
    trigger = DiscoveryTriggerService(session, user.id, discovery_lock=lock)
    queued = trigger.enqueue(max_results=1)
    service = JobDiscoveryService(
        session,
        user.id,
        search=MockSearchProvider(results=[]),
        scraper=MockScraperProvider(),
        llm=MockLLMProvider(content="{}"),
        discovery_lock=lock,
    )
    service.run(workflow_run_id=queued.workflow_run_id, preferences=PreferenceSettings())
    assert lock.get_holder(user.id) is None
    run = session.query(WorkflowRun).filter(WorkflowRun.id == queued.workflow_run_id).one()
    assert run.status == WorkflowRunStatus.completed
