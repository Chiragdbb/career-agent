"""Tests for ApplicationPackageService soft discard."""

from __future__ import annotations

import uuid

import pytest

from database.models.enums import (
    ApplicationStatus,
    CompanyStatus,
    HumanTaskStatus,
    JobMatchStatus,
    JobStatus,
    ResumeStatus,
    ResumeVersionStatus,
    UserStatus,
    WorkflowRunStatus,
)
from database.models.schema import (
    Application,
    Company,
    HumanTask,
    Job,
    JobMatch,
    Resume,
    ResumeVersion,
    User,
    WorkflowRun,
)
from packages.domain.application_package import ApplicationPackageService
from packages.domain.career_workflow import CareerWorkflowService
from packages.domain.exceptions import DomainError
from packages.domain.human_tasks import HumanTaskType


def _session():
    from app.database import get_session_factory

    return get_session_factory()()


@pytest.fixture
def pkg_ctx():
    session = _session()
    user = User(id=uuid.uuid4(), auth_subject=f"pkg-{uuid.uuid4()}", status=UserStatus.active)
    company = Company(id=uuid.uuid4(), name="Pkg Co", status=CompanyStatus.active)
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
        plain_text="Engineer Python",
    )
    match = JobMatch(
        id=uuid.uuid4(),
        user_id=user.id,
        job_id=job.id,
        status=JobMatchStatus.applied,
        score=0.8,
    )
    session.add_all([version, match])
    session.commit()
    app = Application(
        id=uuid.uuid4(),
        user_id=user.id,
        job_id=job.id,
        status=ApplicationStatus.draft,
        resume_version_id=version.id,
        submission_evidence={"draft_materials": {"cover_letter": "Hi"}},
    )
    session.add(app)
    session.commit()
    task = HumanTask(
        id=uuid.uuid4(),
        user_id=user.id,
        task_type=HumanTaskType.approval_required_application,
        title="Approve",
        status=HumanTaskStatus.open,
        application_id=app.id,
        details={"application_id": str(app.id)},
    )
    run = WorkflowRun(
        id=uuid.uuid4(),
        user_id=user.id,
        workflow_type=CareerWorkflowService.WORKFLOW_TYPE,
        status=WorkflowRunStatus.running,
        metadata_json={
            "job_match_id": str(match.id),
            "application_id": str(app.id),
            "paused": True,
        },
    )
    session.add_all([task, run])
    session.commit()
    try:
        yield session, user, app, match, task, run
    finally:
        session.query(HumanTask).filter(HumanTask.user_id == user.id).delete()
        session.query(WorkflowRun).filter(WorkflowRun.user_id == user.id).delete()
        session.query(Application).filter(Application.id == app.id).delete()
        session.query(JobMatch).filter(JobMatch.id == match.id).delete()
        session.query(ResumeVersion).filter(ResumeVersion.id == version.id).delete()
        session.query(Resume).filter(Resume.id == resume.id).delete()
        session.query(Job).filter(Job.id == job.id).delete()
        session.query(Company).filter(Company.id == company.id).delete()
        session.query(User).filter(User.id == user.id).delete()
        session.commit()
        session.close()


def test_return_to_pile_restores_match_and_cancels_tasks(pkg_ctx) -> None:
    session, user, app, match, task, run = pkg_ctx
    result = ApplicationPackageService(session, user.id).return_to_pile(app.id)
    assert result.action == "return_to_pile"
    assert result.match_status == JobMatchStatus.new.value
    session.refresh(app)
    session.refresh(match)
    session.refresh(task)
    session.refresh(run)
    assert app.status == ApplicationStatus.withdrawn
    assert match.status == JobMatchStatus.new
    assert task.status == HumanTaskStatus.cancelled
    assert run.status == WorkflowRunStatus.cancelled


def test_dismiss_package_sets_dismissed(pkg_ctx) -> None:
    session, user, app, match, task, run = pkg_ctx
    result = ApplicationPackageService(session, user.id).dismiss_package(app.id)
    assert result.action == "dismiss"
    assert result.match_status == JobMatchStatus.dismissed.value
    session.refresh(match)
    assert match.status == JobMatchStatus.dismissed


def test_cannot_discard_submitted(pkg_ctx) -> None:
    session, user, app, match, task, run = pkg_ctx
    app.status = ApplicationStatus.submitted
    session.commit()
    with pytest.raises(DomainError):
        ApplicationPackageService(session, user.id).return_to_pile(app.id)
