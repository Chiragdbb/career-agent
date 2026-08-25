"""STEP 14 — JobMatchService deterministic scoring."""

from __future__ import annotations

import uuid

import pytest

from database.models.enums import CompanyStatus, JobStatus, UserStatus
from database.models.schema import Company, Job, JobMatch, User
from packages.domain.job_match import JobMatchService
from packages.domain.preferences import (
    PreferenceSettings,
    SeniorityLevel,
    WorkArrangement,
)


def _session():
    from app.database import get_session_factory

    return get_session_factory()()


@pytest.fixture
def match_ctx():
    session = _session()
    user = User(id=uuid.uuid4(), auth_subject=f"match-{uuid.uuid4()}", status=UserStatus.active)
    company = Company(id=uuid.uuid4(), name="Acme", status=CompanyStatus.active)
    session.add_all([user, company])
    session.commit()
    try:
        yield session, user, company
    finally:
        session.query(JobMatch).filter(JobMatch.user_id == user.id).delete()
        session.query(Job).filter(Job.company_id == company.id).delete()
        session.query(Company).filter(Company.id == company.id).delete()
        session.query(User).filter(User.id == user.id).delete()
        session.commit()
        session.close()


def _job(company_id, **details) -> Job:
    return Job(
        id=uuid.uuid4(),
        company_id=company_id,
        status=JobStatus.active,
        title=details.pop("title", "Backend Engineer"),
        url=f"https://example.com/{uuid.uuid4()}",
        description="desc",
        details=details,
    )


def _prefs(**overrides) -> PreferenceSettings:
    base = PreferenceSettings(
        target_roles=["Backend Engineer"],
        locations=["Remote"],
        work_arrangements=[WorkArrangement.remote],
        minimum_salary=150000,
        seniority=[SeniorityLevel.senior],
    )
    return PreferenceSettings(**{**base.model_dump(), **overrides})


def test_perfect_match_scores_high(match_ctx) -> None:
    session, user, company = match_ctx
    job = _job(
        company.id,
        location="Remote",
        work_arrangement="remote",
        salary_min=160000,
        salary_max=180000,
        skills=["python", "postgres"],
        seniority="senior",
        company_name="Acme",
    )
    session.add(job)
    session.commit()
    service = JobMatchService(session, user.id)
    breakdown = service.score_job(
        job, _prefs(), company_name="Acme", resume_skills=["python", "postgres", "redis"]
    )
    assert breakdown.total >= 0.9
    assert breakdown.role == 1.0
    assert breakdown.salary == 1.0
    assert "missing_salary" not in breakdown.notes


def test_poor_match_scores_low(match_ctx) -> None:
    session, user, company = match_ctx
    job = _job(
        company.id,
        title="Dental Hygienist",
        location="On-site Chicago",
        work_arrangement="on_site",
        salary_min=40000,
        salary_max=50000,
        skills=["dentistry"],
        seniority="entry",
    )
    session.add(job)
    session.commit()
    breakdown = JobMatchService(session, user.id).score_job(
        job, _prefs(), resume_skills=["python"]
    )
    assert breakdown.total <= 0.25


def test_missing_salary_penalized(match_ctx) -> None:
    session, user, company = match_ctx
    job = _job(
        company.id,
        location="Remote",
        work_arrangement="remote",
        skills=["python"],
        seniority="senior",
    )
    session.add(job)
    session.commit()
    breakdown = JobMatchService(session, user.id).score_job(
        job, _prefs(), resume_skills=["python"]
    )
    assert breakdown.salary == 0.0
    assert "missing_salary" in breakdown.notes


def test_remote_mismatch(match_ctx) -> None:
    session, user, company = match_ctx
    job = _job(
        company.id,
        location="New York, NY",
        work_arrangement="on_site",
        salary_min=200000,
        salary_max=220000,
        skills=["python"],
        seniority="senior",
    )
    session.add(job)
    session.commit()
    breakdown = JobMatchService(session, user.id).score_job(
        job, _prefs(), resume_skills=["python"]
    )
    assert breakdown.work_arrangement == 0.0
    assert breakdown.location == 0.0


def test_missing_skills_neutralish(match_ctx) -> None:
    session, user, company = match_ctx
    job = _job(
        company.id,
        location="Remote",
        work_arrangement="remote",
        salary_min=160000,
        salary_max=180000,
        skills=[],
        seniority="senior",
    )
    session.add(job)
    session.commit()
    breakdown = JobMatchService(session, user.id).score_job(job, _prefs(), resume_skills=["python"])
    assert breakdown.skills == 0.5
    assert "missing_skills" in breakdown.notes


def test_upsert_persists_score(match_ctx) -> None:
    session, user, company = match_ctx
    job = _job(
        company.id,
        location="Remote",
        work_arrangement="remote",
        salary_min=160000,
        salary_max=180000,
        skills=["python"],
        seniority="senior",
        company_name="Acme",
    )
    session.add(job)
    session.commit()
    row = JobMatchService(session, user.id).upsert_match(
        job.id, preferences=_prefs(), resume_skills=["python"]
    )
    assert row.score is not None
    assert row.score >= 0.7
    assert row.fit_summary
