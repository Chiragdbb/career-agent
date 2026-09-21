"""Tests for human-readable fit summaries and resume skill harvesting."""

from __future__ import annotations

import uuid

import pytest

from database.models.enums import ResumeStatus, ResumeVersionStatus, UserStatus
from database.models.schema import Resume, ResumeVersion, User
from packages.domain.job_match import ScoreBreakdown, format_fit_summary, format_note
from packages.domain.jobs import load_resume_skills
from packages.domain.resume_models import ExperienceEntry, ProjectEntry, StructuredResume


def _session():
    from app.database import get_session_factory

    return get_session_factory()()


@pytest.fixture
def resume_skill_ctx():
    session = _session()
    user = User(
        id=uuid.uuid4(),
        auth_subject=f"resume-skills-{uuid.uuid4()}",
        status=UserStatus.active,
    )
    session.add(user)
    session.commit()
    try:
        yield session, user
    finally:
        session.query(ResumeVersion).filter(ResumeVersion.user_id == user.id).delete()
        session.query(Resume).filter(Resume.user_id == user.id).delete()
        session.query(User).filter(User.id == user.id).delete()
        session.commit()
        session.close()


def test_format_fit_summary_uses_percentages_and_labels() -> None:
    summary = format_fit_summary(
        ScoreBreakdown(
            total=0.5,
            role=0.5,
            location=0.5,
            work_arrangement=0.5,
            salary=0.5,
            skills=0.5,
            seniority=0.5,
            notes=("missing_skills", "no_resume_skills"),
        )
    )
    assert "Match score: 50%" in summary
    assert "Role 50%" in summary
    assert "missing_skills" not in summary
    assert "Job listing had no skills listed" in summary
    assert "No skills found on your resume" in summary


def test_format_note_fallback() -> None:
    assert format_note("custom_thing") == "Custom thing"


def test_load_resume_skills_harvests_from_text(resume_skill_ctx) -> None:
    session, user = resume_skill_ctx
    resume = Resume(
        id=uuid.uuid4(),
        user_id=user.id,
        name="Primary",
        status=ResumeStatus.active,
    )
    session.add(resume)
    session.flush()
    structured = StructuredResume(
        skills=["Communication"],
        projects=[ProjectEntry(name="API", technologies=["FastAPI"])],
        experience=[
            ExperienceEntry(
                company="Acme",
                title="Engineer",
                bullets=["Used Docker and Kubernetes in production"],
            )
        ],
        summary="Familiar with PostgreSQL and Redis",
    )
    version = ResumeVersion(
        id=uuid.uuid4(),
        resume_id=resume.id,
        user_id=user.id,
        status=ResumeVersionStatus.finalized,
        sections=structured.model_dump(mode="json"),
        plain_text="Also worked with TypeScript and React on the frontend.",
    )
    session.add(version)
    session.commit()

    skills = load_resume_skills(session, user.id)
    lowered = {s.lower() for s in skills}
    assert "communication" in lowered
    assert "fastapi" in lowered
    assert any("docker" in s for s in lowered)
    assert any("kubernetes" in s or "k8s" in s for s in lowered)
    assert any("postgres" in s or "postgresql" in s for s in lowered)
    assert any("typescript" in s for s in lowered)
    assert any("react" in s for s in lowered)
