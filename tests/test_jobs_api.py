"""API tests for job discovery, listing, detail, and re-score."""

from __future__ import annotations

import json
import uuid

import pytest

from database.models.enums import (
    CompanyStatus,
    JobMatchStatus,
    JobStatus,
    UserStatus,
    WorkflowRunStatus,
)
from database.models.schema import Company, Job, JobMatch, User, WorkflowRun


def _session():
    from app.database import get_session_factory

    return get_session_factory()()


def _ensure_user_a(session) -> User:
    user = (
        session.query(User)
        .filter(User.auth_subject == "supabase-user-a")
        .one_or_none()
    )
    if user is None:
        user = User(
            id=uuid.uuid4(),
            auth_subject="supabase-user-a",
            status=UserStatus.active,
        )
        session.add(user)
        session.commit()
    return user


@pytest.fixture
def user_a_job_match(auth_client):
    session = _session()
    user = _ensure_user_a(session)
    company = Company(id=uuid.uuid4(), name="Jobs API Co", status=CompanyStatus.active)
    session.add(company)
    session.flush()
    job = Job(
        id=uuid.uuid4(),
        company_id=company.id,
        title="Platform Engineer",
        status=JobStatus.active,
        url=f"https://example.test/jobs-api/{uuid.uuid4()}",
        description="Build platforms",
        details={
            "location": "Remote",
            "work_arrangement": "remote",
            "salary_min": 160000,
            "salary_max": 190000,
            "skills": ["Python", "Kubernetes"],
            "seniority": "senior",
        },
    )
    session.add(job)
    session.flush()
    match = JobMatch(
        id=uuid.uuid4(),
        user_id=user.id,
        job_id=job.id,
        status=JobMatchStatus.new,
        score=0.82,
        fit_summary="score=0.82; role=1.0; skills=0.5",
    )
    session.add(match)
    session.commit()
    try:
        yield {"match_id": match.id, "job_id": job.id, "user_id": user.id}
    finally:
        session.query(JobMatch).filter(JobMatch.id == match.id).delete()
        session.query(Job).filter(Job.id == job.id).delete()
        session.query(Company).filter(Company.id == company.id).delete()
        session.commit()
        session.close()


def test_list_jobs_returns_tenant_matches(auth_client, user_a_job_match) -> None:
    response = auth_client.get(
        "/api/v1/jobs",
        headers={"Authorization": "Bearer token-user-a"},
    )
    assert response.status_code == 200
    payload = response.json()
    ids = {item["id"] for item in payload}
    assert str(user_a_job_match["match_id"]) in ids
    row = next(item for item in payload if item["id"] == str(user_a_job_match["match_id"]))
    assert row["title"] == "Platform Engineer"
    assert row["company_name"] == "Jobs API Co"
    assert row["score"] == 0.82


def test_get_job_detail_includes_skills(auth_client, user_a_job_match) -> None:
    response = auth_client.get(
        f"/api/v1/jobs/{user_a_job_match['match_id']}",
        headers={"Authorization": "Bearer token-user-a"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "Platform Engineer"
    assert "Python" in payload["job_skills"]
    assert payload["score_breakdown"] is not None
    assert payload["score_breakdown"]["role"] >= 0


def test_rescore_job_updates_score(auth_client, user_a_job_match) -> None:
    response = auth_client.post(
        f"/api/v1/jobs/{user_a_job_match['match_id']}/score",
        headers={"Authorization": "Bearer token-user-a"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["score"] is not None
    assert payload["explanation"]


def test_user_a_cannot_access_user_b_job_match(auth_client, user_b_resources) -> None:
    response = auth_client.get(
        f"/api/v1/jobs/{user_b_resources['job']}",
        headers={"Authorization": "Bearer token-user-a"},
    )
    assert response.status_code == 404


def test_discover_jobs_queues_and_runs_inline(auth_client, monkeypatch) -> None:
    from packages.domain.job_discovery import DiscoveryResult
    from packages.providers.llm import MockLLMProvider
    from packages.providers.scraper import MockScraperProvider, ScrapedPage
    from packages.providers.search import MockSearchProvider, SearchHit

    url = f"https://jobs.example.com/api-test-{uuid.uuid4()}"
    job_payload = json.dumps(
        {
            "title": "API Discovery Engineer",
            "company_name": "Inline Co",
            "location": "Remote",
            "work_arrangement": "remote",
            "salary_min": 150000,
            "salary_max": 170000,
            "skills": ["Python"],
            "url": url,
            "description": "API test job",
        }
    )

    def fake_run(user_id, workflow_run_id, max_results):
        from app.database import get_session_factory, init_db
        from packages.domain.job_discovery import JobDiscoveryService

        init_db()
        session = get_session_factory()()
        try:
            service = JobDiscoveryService(
                session,
                user_id,
                search=MockSearchProvider(
                    results=[SearchHit(title="API", url=url, snippet="x", score=1.0)]
                ),
                scraper=MockScraperProvider(
                    pages=[ScrapedPage(url=url, title="API", markdown="# API job")]
                ),
                llm=MockLLMProvider(content=job_payload),
                max_results=max_results,
            )
            return service.run(workflow_run_id=workflow_run_id)
        finally:
            session.close()

    monkeypatch.setattr("workers.discovery.tasks._run_discovery", fake_run)

    response = auth_client.post(
        "/api/v1/jobs/discover",
        headers={"Authorization": "Bearer token-user-a"},
        json={"max_results": 3, "idempotency_key": f"test-{uuid.uuid4()}"},
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] in {"queued", "completed", "running"}
    assert payload["workflow_run_id"]
    assert payload["task_id"]

    session = _session()
    try:
        run = (
            session.query(WorkflowRun)
            .filter(WorkflowRun.id == uuid.UUID(payload["workflow_run_id"]))
            .one()
        )
        import time

        for _ in range(50):
            session.refresh(run)
            if run.status in (
                WorkflowRunStatus.completed,
                WorkflowRunStatus.failed,
                WorkflowRunStatus.cancelled,
            ):
                break
            time.sleep(0.1)
        assert run.status == WorkflowRunStatus.completed
        matches = session.query(JobMatch).filter(JobMatch.user_id == run.user_id).all()
        assert any(m.score is not None for m in matches)
    finally:
        session.query(JobMatch).filter(JobMatch.user_id == run.user_id).delete()
        session.query(WorkflowRun).filter(WorkflowRun.user_id == run.user_id).delete()
        session.commit()
        session.close()


def test_discover_idempotency_returns_same_run(auth_client) -> None:
    key = f"idempotent-{uuid.uuid4()}"
    headers = {"Authorization": "Bearer token-user-a"}

    first = auth_client.post(
        "/api/v1/jobs/discover",
        headers=headers,
        json={"max_results": 1, "idempotency_key": key},
    )
    assert first.status_code == 202
    second = auth_client.post(
        "/api/v1/jobs/discover",
        headers=headers,
        json={"max_results": 1, "idempotency_key": key},
    )
    assert second.status_code == 202
    assert first.json()["workflow_run_id"] == second.json()["workflow_run_id"]

    session = _session()
    try:
        run_id = uuid.UUID(first.json()["workflow_run_id"])
        session.query(WorkflowRun).filter(WorkflowRun.id == run_id).delete()
        session.commit()
    finally:
        session.close()


def test_get_workflow_run_is_tenant_scoped(auth_client, user_b_resources) -> None:
    session = _session()
    run = WorkflowRun(
        id=uuid.uuid4(),
        user_id=user_b_resources["user_b"],
        status=WorkflowRunStatus.completed,
        workflow_type="job_discovery",
        metadata_json={"test": True},
    )
    session.add(run)
    session.commit()
    try:
        denied = auth_client.get(
            f"/api/v1/workflows/{run.id}",
            headers={"Authorization": "Bearer token-user-a"},
        )
        assert denied.status_code == 404

        allowed = auth_client.get(
            f"/api/v1/workflows/{run.id}",
            headers={"Authorization": "Bearer token-user-b"},
        )
        assert allowed.status_code == 200
        assert allowed.json()["workflow_type"] == "job_discovery"
    finally:
        session.query(WorkflowRun).filter(WorkflowRun.id == run.id).delete()
        session.commit()
        session.close()
