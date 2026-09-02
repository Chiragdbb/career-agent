"""STEP 12 — JobDiscoveryService with mocked providers."""

from __future__ import annotations

import json
import uuid

import pytest

from database.models.enums import UserStatus, WorkflowRunStatus
from database.models.schema import Company, Job, JobMatch, User, WorkflowRun, WorkflowTask
from packages.domain.job_discovery import JobDiscoveryService, normalize_job_url
from packages.domain.preferences import PreferenceSettings, WorkArrangement
from packages.providers.llm import MockLLMProvider
from packages.providers.scraper import MockScraperProvider, ScrapedPage
from packages.providers.search import MockSearchProvider, SearchHit


def _session():
    from app.database import get_session_factory

    return get_session_factory()()


def _user(session) -> User:
    user = User(id=uuid.uuid4(), auth_subject=f"discovery-{uuid.uuid4()}", status=UserStatus.active)
    session.add(user)
    session.commit()
    return user


def _cleanup(session, user_id: uuid.UUID) -> None:
    session.query(WorkflowTask).filter(WorkflowTask.user_id == user_id).delete()
    session.query(WorkflowRun).filter(WorkflowRun.user_id == user_id).delete()
    session.query(JobMatch).filter(JobMatch.user_id == user_id).delete()
    # Jobs/companies may be shared; only delete jobs created in these tests via matches cleanup path.
    job_ids = [
        row.job_id
        for row in session.query(JobMatch).filter(JobMatch.user_id == user_id).all()
    ]
    session.query(JobMatch).filter(JobMatch.user_id == user_id).delete()
    if job_ids:
        session.query(Job).filter(Job.id.in_(job_ids)).delete(synchronize_session=False)
    session.commit()


@pytest.fixture
def discovery_user():
    session = _session()
    user = _user(session)
    try:
        yield session, user
    finally:
        session.query(WorkflowTask).filter(WorkflowTask.user_id == user.id).delete()
        session.query(WorkflowRun).filter(WorkflowRun.user_id == user.id).delete()
        matches = session.query(JobMatch).filter(JobMatch.user_id == user.id).all()
        job_ids = [m.job_id for m in matches]
        session.query(JobMatch).filter(JobMatch.user_id == user.id).delete()
        if job_ids:
            session.query(Job).filter(Job.id.in_(job_ids)).delete(synchronize_session=False)
        session.query(User).filter(User.id == user.id).delete()
        session.commit()
        session.close()


def _job_json(**overrides):
    base = {
        "title": "Backend Engineer",
        "company_name": "Acme Corp",
        "location": "Remote",
        "work_arrangement": "remote",
        "salary_min": 150000,
        "salary_max": 180000,
        "skills": ["Python", "Postgres"],
        "url": "https://jobs.example.com/backend-1",
        "description": "Build APIs",
    }
    base.update(overrides)
    return json.dumps(base)


def test_normalize_job_url_strips_tracking() -> None:
    assert (
        normalize_job_url("https://Jobs.Example.com/role/?utm_source=x#frag")
        == "https://jobs.example.com/role"
    )


def test_discovery_creates_job_and_is_idempotent(discovery_user) -> None:
    session, user = discovery_user
    url = f"https://jobs.example.com/backend-{uuid.uuid4()}"
    search = MockSearchProvider(
        results=[SearchHit(title="Backend", url=url, snippet="Acme", score=1.0)]
    )
    scraper = MockScraperProvider(
        pages=[ScrapedPage(url=url, title="Backend", markdown="# Backend Engineer at Acme")]
    )
    llm = MockLLMProvider(content=_job_json(url=url))
    service = JobDiscoveryService(
        session, user.id, search=search, scraper=scraper, llm=llm, max_results=3
    )
    prefs = PreferenceSettings(
        target_roles=["Backend Engineer"],
        locations=["Remote"],
        work_arrangements=[WorkArrangement.remote],
    )
    first = service.run(preferences=prefs)
    assert len(first.created_jobs) == 1
    assert first.skipped_invalid == 0
    run = session.query(WorkflowRun).filter(WorkflowRun.id == first.workflow_run_id).one()
    assert run.status == WorkflowRunStatus.completed

    second = JobDiscoveryService(
        session, user.id, search=search, scraper=scraper, llm=llm, max_results=3
    ).run(preferences=prefs)
    assert first.created_jobs[0] in second.duplicate_jobs
    assert len(second.created_jobs) == 0
    jobs = session.query(Job).filter(Job.url == normalize_job_url(url)).all()
    assert len(jobs) == 1


def test_discovery_skips_fresh_scrape_on_second_run(discovery_user) -> None:
    session, user = discovery_user
    url = f"https://jobs.example.com/fresh-{uuid.uuid4()}"
    search = MockSearchProvider(
        results=[SearchHit(title="Backend", url=url, snippet="Acme", score=1.0)]
    )
    scrape_calls = {"count": 0}

    class CountingScraper(MockScraperProvider):
        def scrape_url(self, request):
            scrape_calls["count"] += 1
            return super().scrape_url(request)

    scraper = CountingScraper(
        pages=[ScrapedPage(url=url, title="Backend", markdown="# Backend Engineer at Acme")]
    )
    llm = MockLLMProvider(content=_job_json(url=url))
    prefs = PreferenceSettings(target_roles=["Backend Engineer"], locations=["Remote"])

    first = JobDiscoveryService(
        session, user.id, search=search, scraper=scraper, llm=llm, max_results=3
    ).run(preferences=prefs)
    assert len(first.created_jobs) == 1
    assert scrape_calls["count"] == 1

    second = JobDiscoveryService(
        session, user.id, search=search, scraper=scraper, llm=llm, max_results=3
    ).run(preferences=prefs)
    assert first.created_jobs[0] in second.duplicate_jobs
    assert scrape_calls["count"] == 1


def test_discovery_skips_malformed_llm(discovery_user) -> None:
    session, user = discovery_user
    url = f"https://jobs.example.com/bad-{uuid.uuid4()}"
    search = MockSearchProvider(results=[SearchHit(title="X", url=url, snippet="")])
    scraper = MockScraperProvider(pages=[ScrapedPage(url=url, markdown="junk")])
    llm = MockLLMProvider(content="not-json")
    result = JobDiscoveryService(
        session, user.id, search=search, scraper=scraper, llm=llm
    ).run(preferences=PreferenceSettings(target_roles=["Engineer"]))
    assert result.created_jobs == []
    assert result.skipped_invalid == 1


def test_discovery_accepts_missing_salary_location_company(discovery_user) -> None:
    session, user = discovery_user
    url = f"https://jobs.example.com/sparse-{uuid.uuid4()}"
    search = MockSearchProvider(results=[SearchHit(title="Eng", url=url, snippet="")])
    scraper = MockScraperProvider(pages=[ScrapedPage(url=url, markdown="Engineer")])
    llm = MockLLMProvider(
        content=_job_json(
            url=url,
            company_name=None,
            location=None,
            salary_min=None,
            salary_max=None,
            work_arrangement=None,
        )
    )
    result = JobDiscoveryService(
        session, user.id, search=search, scraper=scraper, llm=llm
    ).run(preferences=PreferenceSettings(target_roles=["Engineer"]))
    assert len(result.created_jobs) == 1
    job = session.query(Job).filter(Job.id == result.created_jobs[0]).one()
    company = session.query(Company).filter(Company.id == job.company_id).one()
    assert company.name == "Unknown Company"
    assert job.details.get("salary_min") is None
    assert job.details.get("location") is None
