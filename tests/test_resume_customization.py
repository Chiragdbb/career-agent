"""STEP 18 — ResumeCustomizationService rejects fabrications."""

from __future__ import annotations

import uuid

import pytest

from database.models.enums import (
    CompanyStatus,
    JobMatchStatus,
    JobStatus,
    ResumeStatus,
    ResumeVersionStatus,
    UserStatus,
)
from database.models.schema import Company, Job, JobMatch, Resume, ResumeVersion, User
from packages.domain.exceptions import DomainError
from packages.domain.resume_customization import ResumeCustomizationService
from packages.domain.resume_models import (
    ExperienceEntry,
    StructuredResume,
    ContactInfo,
)
from packages.domain.resume_validation import validate_against_canonical


def _session():
    from app.database import get_session_factory

    return get_session_factory()()


def _canonical() -> StructuredResume:
    return StructuredResume(
        contact=ContactInfo(full_name="Pat Candidate", email="pat@example.com"),
        summary="Backend engineer with Python and Postgres experience.",
        skills=["Python", "Postgres", "FastAPI"],
        experience=[
            ExperienceEntry(
                company="PastCo",
                title="Software Engineer",
                start_date="2020",
                end_date="2023",
                bullets=[
                    "Built APIs in Python",
                    "Improved query latency by 30%",
                ],
            )
        ],
    )


@pytest.fixture
def customize_ctx():
    session = _session()
    user = User(id=uuid.uuid4(), auth_subject=f"custom-{uuid.uuid4()}", status=UserStatus.active)
    company = Company(id=uuid.uuid4(), name="HireCo", status=CompanyStatus.active)
    session.add_all([user, company])
    session.commit()
    job = Job(
        id=uuid.uuid4(),
        company_id=company.id,
        title="Python Engineer",
        status=JobStatus.active,
        url=f"https://hire.example/jobs/{uuid.uuid4()}",
        details={"skills": ["Python", "FastAPI"]},
    )
    resume = Resume(
        id=uuid.uuid4(),
        user_id=user.id,
        name="Master",
        status=ResumeStatus.active,
    )
    session.add_all([job, resume])
    session.commit()
    version = ResumeVersion(
        id=uuid.uuid4(),
        resume_id=resume.id,
        user_id=user.id,
        status=ResumeVersionStatus.finalized,
        sections=_canonical().model_dump(),
        plain_text="canonical",
    )
    match = JobMatch(
        id=uuid.uuid4(),
        user_id=user.id,
        job_id=job.id,
        status=JobMatchStatus.new,
        score=0.88,
    )
    session.add_all([version, match])
    session.commit()
    try:
        yield session, user, resume, match
    finally:
        session.query(ResumeVersion).filter(ResumeVersion.user_id == user.id).delete()
        session.query(JobMatch).filter(JobMatch.user_id == user.id).delete()
        session.query(Resume).filter(Resume.id == resume.id).delete()
        session.query(Job).filter(Job.id == job.id).delete()
        session.query(Company).filter(Company.id == company.id).delete()
        session.query(User).filter(User.id == user.id).delete()
        session.commit()
        session.close()


def test_rejects_invented_employer() -> None:
    canonical = _canonical()
    fake = StructuredResume.model_validate(canonical.model_dump())
    fake.experience.append(
        ExperienceEntry(company="TotallyFakeCorp", title="CEO", start_date="2019", end_date="2020")
    )
    issues = validate_against_canonical(canonical, fake)
    assert any(i.field == "experience.company" for i in issues)


def test_rejects_invented_metric() -> None:
    canonical = _canonical()
    fake = StructuredResume.model_validate(canonical.model_dump())
    fake.summary = "Increased revenue by 400% and scaled to 10M users"
    issues = validate_against_canonical(canonical, fake)
    assert any("Metric" in i.detail for i in issues)


def test_customize_reorders_without_fabrication(customize_ctx) -> None:
    session, user, resume, match = customize_ctx
    service = ResumeCustomizationService(session, user.id)
    version = service.customize_for_match(
        resume_id=resume.id,
        job_match_id=match.id,
        emphasis_skills=["Python"],
        max_bullets_per_role=2,
    )
    assert version.status == ResumeVersionStatus.draft
    structured = StructuredResume.model_validate(version.sections)
    assert structured.skills[0] == "Python"
    assert "TotallyFakeCorp" not in (version.plain_text or "")


def test_customize_rejects_bad_summary_override(customize_ctx) -> None:
    session, user, resume, match = customize_ctx
    service = ResumeCustomizationService(session, user.id)
    with pytest.raises(DomainError, match="Unsupported"):
        service.customize_for_match(
            resume_id=resume.id,
            job_match_id=match.id,
            summary_override="Grew ARR by $5M at FakeCorp using QuantumML",
        )
