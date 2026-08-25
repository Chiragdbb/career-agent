"""STEP 22 — ApplicationEngine state machine transitions."""

from __future__ import annotations

import uuid

import pytest

from database.models.enums import (
    ApplicationStatus,
    CompanyStatus,
    JobStatus,
    ResumeStatus,
    ResumeVersionStatus,
    UserStatus,
)
from database.models.schema import (
    Application,
    ApplicationEvent,
    Company,
    Job,
    Resume,
    ResumeVersion,
    User,
)
from packages.domain.application_engine import (
    VALID_TRANSITIONS,
    ApplicationEngine,
    EngineState,
)
from packages.domain.exceptions import DomainError


def _session():
    from app.database import get_session_factory

    return get_session_factory()()


@pytest.fixture
def engine_ctx():
    session = _session()
    user = User(id=uuid.uuid4(), auth_subject=f"engine-{uuid.uuid4()}", status=UserStatus.active)
    company = Company(id=uuid.uuid4(), name="EngineCo", status=CompanyStatus.active)
    session.add_all([user, company])
    session.commit()
    job = Job(
        id=uuid.uuid4(),
        company_id=company.id,
        title="Engineer",
        status=JobStatus.active,
        url=f"https://engine.example/jobs/{uuid.uuid4()}",
    )
    resume = Resume(id=uuid.uuid4(), user_id=user.id, name="R", status=ResumeStatus.active)
    session.add_all([job, resume])
    session.commit()
    version = ResumeVersion(
        id=uuid.uuid4(),
        resume_id=resume.id,
        user_id=user.id,
        status=ResumeVersionStatus.finalized,
        plain_text="x",
    )
    session.add(version)
    session.commit()
    app = Application(
        id=uuid.uuid4(),
        user_id=user.id,
        job_id=job.id,
        resume_version_id=version.id,
        status=ApplicationStatus.draft,
        submission_evidence={"engine_status": EngineState.PREPARED.value},
    )
    session.add(app)
    session.commit()
    try:
        yield session, user, app
    finally:
        session.query(ApplicationEvent).filter(ApplicationEvent.user_id == user.id).delete()
        session.query(Application).filter(Application.id == app.id).delete()
        session.query(ResumeVersion).filter(ResumeVersion.user_id == user.id).delete()
        session.query(Resume).filter(Resume.id == resume.id).delete()
        session.query(Job).filter(Job.id == job.id).delete()
        session.query(Company).filter(Company.id == company.id).delete()
        session.query(User).filter(User.id == user.id).delete()
        session.commit()
        session.close()


def test_all_valid_transitions_documented() -> None:
    # Every state appears; SUBMITTED is terminal.
    assert EngineState.SUBMITTED in VALID_TRANSITIONS
    assert VALID_TRANSITIONS[EngineState.SUBMITTED] == frozenset()
    for state in EngineState:
        assert state in VALID_TRANSITIONS


def test_valid_happy_path_to_submitted(engine_ctx) -> None:
    session, user, app = engine_ctx
    engine = ApplicationEngine(session, user.id)
    engine.transition(app.id, EngineState.AWAITING_APPROVAL, reason="ready_for_review")
    engine.transition(app.id, EngineState.IN_PROGRESS, reason="approved")
    result = engine.transition(
        app.id,
        EngineState.SUBMITTED,
        evidence={"confirmation_id": "APP-12345", "confirmation_url": "https://portal/confirm/1"},
    )
    assert result.to_state == EngineState.SUBMITTED
    session.refresh(app)
    assert app.status == ApplicationStatus.submitted
    assert app.applied_at is not None
    events = session.query(ApplicationEvent).filter(ApplicationEvent.application_id == app.id).all()
    assert len(events) == 3
    assert any("PREPARED->AWAITING_APPROVAL" in e.event_type for e in events)


def test_submitted_without_evidence_rejected(engine_ctx) -> None:
    session, user, app = engine_ctx
    engine = ApplicationEngine(session, user.id)
    engine.transition(app.id, EngineState.AWAITING_APPROVAL)
    engine.transition(app.id, EngineState.IN_PROGRESS)
    with pytest.raises(DomainError, match="evidence"):
        engine.transition(app.id, EngineState.SUBMITTED, evidence={})


def test_invalid_transition_rejected(engine_ctx) -> None:
    session, user, app = engine_ctx
    engine = ApplicationEngine(session, user.id)
    with pytest.raises(DomainError, match="Invalid transition"):
        engine.transition(app.id, EngineState.SUBMITTED, evidence={"confirmation_id": "x"})


def test_requires_human_for_captcha_and_unknown(engine_ctx) -> None:
    session, user, app = engine_ctx
    engine = ApplicationEngine(session, user.id)
    engine.transition(app.id, EngineState.AWAITING_APPROVAL)
    engine.transition(app.id, EngineState.IN_PROGRESS)
    result = engine.mark_requires_human(app.id, human_reason="captcha")
    assert result.to_state == EngineState.REQUIRES_HUMAN
    assert result.evidence["human_reason"] == "captcha"

    engine.transition(app.id, EngineState.IN_PROGRESS, reason="human_resolved")
    result2 = engine.mark_requires_human(app.id, human_reason="unknown_question")
    assert result2.evidence["human_reason"] == "unknown_question"


@pytest.mark.parametrize(
    "from_state,to_state",
    [
        (EngineState.PREPARED, EngineState.IN_PROGRESS),
        (EngineState.SUBMITTED, EngineState.PREPARED),
        (EngineState.BLOCKED, EngineState.SUBMITTED),
        (EngineState.FAILED, EngineState.IN_PROGRESS),
    ],
)
def test_invalid_pairs(from_state: EngineState, to_state: EngineState, engine_ctx) -> None:
    session, user, app = engine_ctx
    engine = ApplicationEngine(session, user.id)
    # Force starting state
    app.submission_evidence = {"engine_status": from_state.value}
    session.commit()
    assert engine.can_transition(from_state, to_state) is False
    with pytest.raises(DomainError):
        engine.transition(
            app.id,
            to_state,
            evidence={"confirmation_id": "x"} if to_state == EngineState.SUBMITTED else None,
        )


def test_every_valid_transition_succeeds(engine_ctx) -> None:
    """Exercise each allowed edge at least once (fresh app per edge via state reset)."""
    session, user, app = engine_ctx
    engine = ApplicationEngine(session, user.id)
    for current, targets in VALID_TRANSITIONS.items():
        for target in targets:
            app.submission_evidence = {"engine_status": current.value}
            if current == EngineState.SUBMITTED:
                app.status = ApplicationStatus.submitted
            elif current in (EngineState.IN_PROGRESS, EngineState.REQUIRES_HUMAN):
                app.status = ApplicationStatus.in_progress
            else:
                app.status = ApplicationStatus.draft
            session.commit()
            evidence = None
            if target == EngineState.SUBMITTED:
                evidence = {"portal_application_id": "P-1"}
            result = engine.transition(app.id, target, reason="param_test", evidence=evidence)
            assert result.to_state == target
