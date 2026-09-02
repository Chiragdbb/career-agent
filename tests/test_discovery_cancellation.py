"""Tests for cooperative discovery cancellation."""

from __future__ import annotations

import time
import uuid

import pytest

from database.models.enums import UserStatus, WorkflowRunStatus
from database.models.schema import User, WorkflowRun
from packages.domain.discovery_lock import DiscoveryLock
from packages.domain.job_discovery import JobDiscoveryService
from packages.domain.jobs import DiscoveryTriggerService
from packages.domain.preferences import PreferenceSettings
from packages.domain.workflow_cancellation import WorkflowCancellation
from packages.providers.llm import MockLLMProvider
from packages.providers.scraper import MockScraperProvider, ScrapedPage
from packages.providers.search import MockSearchProvider, SearchHit


class FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def setex(self, name: str, time: int, value: str) -> None:
        self._store[name] = value

    def get(self, name: str) -> str | None:
        return self._store.get(name)

    def delete(self, name: str) -> int:
        if name in self._store:
            del self._store[name]
            return 1
        return 0

    def set(self, name: str, value: str, nx: bool = False, ex: int | None = None) -> bool:
        if nx and name in self._store:
            return False
        self._store[name] = value
        return True


def _session():
    from app.database import get_session_factory

    return get_session_factory()()


@pytest.fixture
def cancel_user():
    session = _session()
    user = User(id=uuid.uuid4(), auth_subject=f"cancel-{uuid.uuid4()}", status=UserStatus.active)
    session.add(user)
    session.commit()
    redis = FakeRedis()
    try:
        yield session, user, redis
    finally:
        session.query(WorkflowRun).filter(WorkflowRun.user_id == user.id).delete()
        session.query(User).filter(User.id == user.id).delete()
        session.commit()
        session.close()


def test_cancel_before_run_results_in_cancelled(cancel_user) -> None:
    session, user, redis = cancel_user
    lock = DiscoveryLock(redis)
    cancellation = WorkflowCancellation(redis)
    trigger = DiscoveryTriggerService(session, user.id, discovery_lock=lock)
    queued = trigger.enqueue(max_results=1)

    url = f"https://jobs.example.com/cancel-{uuid.uuid4()}"
    search = MockSearchProvider(results=[SearchHit(title="A", url=url, snippet="")])
    scraper = MockScraperProvider(pages=[ScrapedPage(url=url, markdown="# Job A")])
    scrape_calls = {"count": 0}

    class CountingScraper(MockScraperProvider):
        def scrape_url(self, request):
            scrape_calls["count"] += 1
            return super().scrape_url(request)

    scraper = CountingScraper(pages=[ScrapedPage(url=url, markdown="# Job A")])
    job_json = (
        '{"title":"Eng","company_name":"Co","url":"'
        + url
        + '","description":"d","skills":["Python"]}'
    )

    trigger.cancel(queued.workflow_run_id, cancellation=cancellation)
    service = JobDiscoveryService(
        session,
        user.id,
        search=search,
        scraper=scraper,
        llm=MockLLMProvider(content=job_json),
        cancellation=cancellation,
        discovery_lock=lock,
    )
    service.run(workflow_run_id=queued.workflow_run_id, preferences=PreferenceSettings(target_roles=["Eng"]))
    run = session.query(WorkflowRun).filter(WorkflowRun.id == queued.workflow_run_id).one()
    assert run.status == WorkflowRunStatus.cancelled
    assert lock.get_holder(user.id) is None
    assert scrape_calls["count"] == 0
