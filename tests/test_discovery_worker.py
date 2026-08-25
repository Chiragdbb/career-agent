"""Celery discovery worker task tests."""

from __future__ import annotations

import json
import uuid

import pytest

from database.models.enums import UserStatus, WorkflowRunStatus
from database.models.schema import User, WorkflowRun
from packages.providers.llm import MockLLMProvider
from packages.providers.scraper import MockScraperProvider, ScrapedPage
from packages.providers.search import MockSearchProvider, SearchHit


def _session():
    from app.database import get_session_factory

    return get_session_factory()()


@pytest.fixture
def worker_user():
    session = _session()
    user = User(id=uuid.uuid4(), auth_subject=f"worker-{uuid.uuid4()}", status=UserStatus.active)
    session.add(user)
    session.commit()
    run = WorkflowRun(
        id=uuid.uuid4(),
        user_id=user.id,
        status=WorkflowRunStatus.queued,
        workflow_type="job_discovery",
        metadata_json={"max_results": 2},
    )
    session.add(run)
    session.commit()
    try:
        yield session, user, run
    finally:
        from database.models.schema import JobMatch, WorkflowTask

        session.query(WorkflowTask).filter(WorkflowTask.user_id == user.id).delete()
        session.query(JobMatch).filter(JobMatch.user_id == user.id).delete()
        session.query(WorkflowRun).filter(WorkflowRun.user_id == user.id).delete()
        session.query(User).filter(User.id == user.id).delete()
        session.commit()
        session.close()


def test_discover_jobs_task_runs_with_mocks(worker_user, monkeypatch) -> None:
    session, user, run = worker_user
    url = f"https://worker.example/job-{uuid.uuid4()}"
    job_json = json.dumps(
        {
            "title": "Worker Engineer",
            "company_name": "Worker Co",
            "location": "Remote",
            "work_arrangement": "remote",
            "skills": ["Python"],
            "url": url,
            "description": "Worker test",
        }
    )

    monkeypatch.setattr(
        "workers.discovery.tasks.create_search_provider",
        lambda settings=None: MockSearchProvider(
            results=[SearchHit(title="Worker", url=url, snippet="", score=1.0)]
        ),
    )
    monkeypatch.setattr(
        "workers.discovery.tasks.create_scraper_provider",
        lambda settings=None: MockScraperProvider(
            pages=[ScrapedPage(url=url, title="Worker", markdown="# Worker job")]
        ),
    )
    monkeypatch.setattr(
        "workers.discovery.tasks.create_llm_provider",
        lambda settings=None: MockLLMProvider(content=job_json),
    )

    from workers.discovery.tasks import discover_jobs

    result = discover_jobs.run(str(user.id), str(run.id), 2)
    session.expire_all()
    refreshed = session.query(WorkflowRun).filter(WorkflowRun.id == run.id).one()
    assert refreshed.status == WorkflowRunStatus.completed
    assert result["created_jobs"]
    assert result["skipped_invalid"] == 0
