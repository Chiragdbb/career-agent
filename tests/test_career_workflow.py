"""STEP 28–29 — Celery expansion smoke + CareerWorkflowService tests."""

from __future__ import annotations

import uuid

import pytest

from database.models.enums import (
    CompanyStatus,
    HumanTaskStatus,
    JobMatchStatus,
    JobStatus,
    ResumeStatus,
    ResumeVersionStatus,
    UserStatus,
)
from database.models.schema import (
    Application,
    ApplicationEvent,
    Company,
    HumanTask,
    Job,
    JobMatch,
    Notification,
    Resume,
    ResumeVersion,
    User,
    WorkflowRun,
    WorkflowTask,
)
from packages.domain.career_workflow import (
    CareerWorkflowService,
    CareerWorkflowStart,
)
from packages.domain.human_tasks import HumanTaskResolveInput, HumanTaskService
from packages.providers.notification import MockNotificationProvider
from workers.celery_app import celery_app


def _session():
    from app.database import get_session_factory

    return get_session_factory()()


@pytest.fixture
def wf_ctx():
    session = _session()
    user = User(id=uuid.uuid4(), auth_subject=f"wf-{uuid.uuid4()}", status=UserStatus.active)
    company = Company(id=uuid.uuid4(), name="WF Co", status=CompanyStatus.active)
    session.add_all([user, company])
    session.commit()
    job = Job(
        id=uuid.uuid4(),
        company_id=company.id,
        title="Staff Engineer",
        status=JobStatus.active,
        url=f"https://boards.greenhouse.io/wfco/jobs/{uuid.uuid4().int % 10**7}",
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
    session.add(version)
    session.commit()
    match = JobMatch(
        id=uuid.uuid4(),
        user_id=user.id,
        job_id=job.id,
        status=JobMatchStatus.new,
        score=0.85,
    )
    session.add(match)
    session.commit()
    notif = MockNotificationProvider()
    try:
        yield session, user, match, version, notif
    finally:
        session.query(Notification).filter(Notification.user_id == user.id).delete()
        session.query(HumanTask).filter(HumanTask.user_id == user.id).delete()
        session.query(ApplicationEvent).filter(ApplicationEvent.user_id == user.id).delete()
        session.query(Application).filter(Application.user_id == user.id).delete()
        session.query(WorkflowTask).filter(WorkflowTask.user_id == user.id).delete()
        session.query(WorkflowRun).filter(WorkflowRun.user_id == user.id).delete()
        session.query(JobMatch).filter(JobMatch.id == match.id).delete()
        session.query(ResumeVersion).filter(ResumeVersion.id == version.id).delete()
        session.query(Resume).filter(Resume.id == resume.id).delete()
        session.query(Job).filter(Job.id == job.id).delete()
        session.query(Company).filter(Company.id == company.id).delete()
        session.query(User).filter(User.id == user.id).delete()
        session.commit()
        session.close()


def test_celery_includes_expanded_workers() -> None:
    includes = set(celery_app.conf.include or [])
    for mod in (
        "workers.discovery.tasks",
        "workers.research.tasks",
        "workers.contacts.tasks",
        "workers.documents.tasks",
        "workers.applications.tasks",
        "workers.outreach.tasks",
        "workers.notifications.tasks",
    ):
        assert mod in includes


def test_career_workflow_pauses_for_approval_then_resumes(wf_ctx) -> None:
    session, user, match, version, notif = wf_ctx
    svc = CareerWorkflowService(session, user.id, notifications=notif)
    result = svc.start_or_resume(
        CareerWorkflowStart(
            job_match_id=match.id,
            resume_version_id=version.id,
            permit_submit=False,
        )
    )
    assert result.paused is True
    assert result.human_task_id is not None
    assert "approval_pause" in result.completed_steps
    assert result.application_id is not None

    # Resolve human task and resume.
    ht = HumanTaskService(session, user.id, notifications=notif)
    ht.resolve(
        result.human_task_id,
        HumanTaskResolveInput(resolution={"approved": True}, resume_workflow=True),
    )
    resumed = svc.start_or_resume(
        CareerWorkflowStart(
            job_match_id=match.id,
            resume_version_id=version.id,
            permit_submit=False,
            force=True,
        )
    )
    assert resumed.paused is False
    assert resumed.status == "completed"
    assert "notify" in resumed.completed_steps
    assert resumed.outputs.get("submitted") is False or (
        resumed.outputs.get("reason") and "not permitted" in str(resumed.outputs.get("reason", ""))
        or "evidence" in str(resumed.outputs.get("reason", "")).lower()
        or resumed.outputs.get("follow_up")
    )
    # Never SUBMITTED without evidence — application should not be submitted status.
    app = session.query(Application).filter(Application.id == resumed.application_id).one()
    assert app.status.value != "submitted"


def test_career_workflow_idempotent_completed_steps(wf_ctx) -> None:
    session, user, match, version, notif = wf_ctx
    svc = CareerWorkflowService(session, user.id, notifications=notif)
    first = svc.start_or_resume(
        CareerWorkflowStart(job_match_id=match.id, resume_version_id=version.id)
    )
    assert first.paused is True
    # Second call without force returns paused state (idempotent).
    second = svc.start_or_resume(
        CareerWorkflowStart(job_match_id=match.id, resume_version_id=version.id)
    )
    assert second.paused is True
    assert second.workflow_run_id == first.workflow_run_id
    open_tasks = (
        session.query(HumanTask)
        .filter(HumanTask.user_id == user.id, HumanTask.status == HumanTaskStatus.open)
        .count()
    )
    assert open_tasks == 1
