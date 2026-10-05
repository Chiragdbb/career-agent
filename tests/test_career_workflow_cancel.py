"""Career pipeline cancel must stay cancelled (never overwritten to failed)."""

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
    WorkflowRunStatus,
)
from database.models.schema import (
    Company,
    Job,
    JobMatch,
    Resume,
    ResumeVersion,
    User,
    WorkflowRun,
)
from packages.domain.career_workflow import CareerWorkflowService, CareerWorkflowStart
from packages.domain.jobs import DiscoveryTriggerService
from packages.domain.workflow_cancellation import WorkflowCancellation
from packages.providers.notification import MockNotificationProvider


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


def _session():
    from app.database import get_session_factory

    return get_session_factory()()


@pytest.fixture
def cancel_ctx():
    session = _session()
    user = User(id=uuid.uuid4(), auth_subject=f"cxl-{uuid.uuid4()}", status=UserStatus.active)
    company = Company(id=uuid.uuid4(), name="Cancel Co", status=CompanyStatus.active)
    session.add_all([user, company])
    session.commit()
    job = Job(
        id=uuid.uuid4(),
        company_id=company.id,
        title="Engineer",
        status=JobStatus.active,
        url=f"https://example.com/jobs/{uuid.uuid4()}",
    )
    resume = Resume(id=uuid.uuid4(), user_id=user.id, name="Master", status=ResumeStatus.active)
    session.add_all([job, resume])
    session.commit()
    version = ResumeVersion(
        id=uuid.uuid4(),
        resume_id=resume.id,
        user_id=user.id,
        status=ResumeVersionStatus.finalized,
        plain_text="Engineer",
    )
    match = JobMatch(
        id=uuid.uuid4(),
        user_id=user.id,
        job_id=job.id,
        status=JobMatchStatus.new,
        score=0.9,
    )
    session.add_all([version, match])
    session.commit()
    redis = FakeRedis()
    try:
        yield session, user, match, version, redis
    finally:
        session.query(WorkflowRun).filter(WorkflowRun.user_id == user.id).delete()
        session.query(JobMatch).filter(JobMatch.id == match.id).delete()
        session.query(ResumeVersion).filter(ResumeVersion.id == version.id).delete()
        session.query(Resume).filter(Resume.id == resume.id).delete()
        session.query(Job).filter(Job.id == job.id).delete()
        session.query(Company).filter(Company.id == company.id).delete()
        session.query(User).filter(User.id == user.id).delete()
        session.commit()
        session.close()


def test_cancel_during_pipeline_does_not_mark_failed(cancel_ctx) -> None:
    session, user, match, version, redis = cancel_ctx
    cancellation = WorkflowCancellation(redis)
    calls = {"people": 0}

    def people_fn(s, uid, company_id):
        calls["people"] += 1
        # Simulate user cancel mid-step between checkpoints.
        trigger = DiscoveryTriggerService(session, user.id)
        run = (
            session.query(WorkflowRun)
            .filter(
                WorkflowRun.user_id == user.id,
                WorkflowRun.workflow_type == "career_job_pipeline",
            )
            .order_by(WorkflowRun.created_at.desc())
            .first()
        )
        assert run is not None
        trigger.cancel(run.id, cancellation=cancellation)
        return {"people": [], "contact_count": 0, "company_id": str(company_id)}

    svc = CareerWorkflowService(
        session,
        user.id,
        notifications=MockNotificationProvider(),
        cancellation=cancellation,
        people_fn=people_fn,
    )
    result = svc.start_or_resume(
        CareerWorkflowStart(
            job_match_id=match.id,
            resume_version_id=version.id,
            override_completeness=True,
        )
    )
    assert result.status == "cancelled"
    assert calls["people"] == 1
    run = session.query(WorkflowRun).filter(WorkflowRun.id == result.workflow_run_id).one()
    assert run.status == WorkflowRunStatus.cancelled
    assert run.error is None
    assert (run.metadata_json or {}).get("current_step") == "cancelled"
    assert (run.metadata_json or {}).get("paused") is False
