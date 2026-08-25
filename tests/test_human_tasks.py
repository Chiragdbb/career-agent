"""STEP 24 — HumanTaskService tests."""

from __future__ import annotations

import uuid

import pytest

from database.models.enums import UserStatus, WorkflowRunStatus
from database.models.schema import HumanTask, Notification, User, WorkflowRun
from packages.domain.human_tasks import (
    HumanTaskCreate,
    HumanTaskResolveInput,
    HumanTaskService,
    HumanTaskType,
)
from packages.providers.notification import MockNotificationProvider


def _session():
    from app.database import get_session_factory

    return get_session_factory()()


@pytest.fixture
def ht_ctx():
    session = _session()
    user = User(id=uuid.uuid4(), auth_subject=f"ht-{uuid.uuid4()}", status=UserStatus.active)
    run = WorkflowRun(
        id=uuid.uuid4(),
        user_id=user.id,
        status=WorkflowRunStatus.running,
        workflow_type="career_job_pipeline",
        metadata_json={"paused": False},
    )
    session.add_all([user, run])
    session.commit()
    notif = MockNotificationProvider()
    try:
        yield session, user, run, notif
    finally:
        session.query(Notification).filter(Notification.user_id == user.id).delete()
        session.query(HumanTask).filter(HumanTask.user_id == user.id).delete()
        session.query(WorkflowRun).filter(WorkflowRun.id == run.id).delete()
        session.query(User).filter(User.id == user.id).delete()
        session.commit()
        session.close()


def test_create_pauses_workflow_and_notifies(ht_ctx) -> None:
    session, user, run, notif = ht_ctx
    svc = HumanTaskService(session, user.id, notifications=notif)
    view = svc.create(
        HumanTaskCreate(
            task_type=HumanTaskType.captcha,
            title="Solve CAPTCHA",
            details={"ats": "greenhouse"},
            workflow_run_id=run.id,
        )
    )
    assert view.status == "open"
    assert len(notif.sent) == 1
    session.refresh(run)
    assert run.metadata_json["paused"] is True
    assert run.metadata_json["pause_human_task_id"] == str(view.id)


def test_resolve_resumes_workflow(ht_ctx) -> None:
    session, user, run, notif = ht_ctx
    svc = HumanTaskService(session, user.id, notifications=notif)
    view = svc.create(
        HumanTaskCreate(
            task_type=HumanTaskType.unknown_question,
            title="Answer Q",
            workflow_run_id=run.id,
        )
    )
    resolved = svc.resolve(
        view.id,
        HumanTaskResolveInput(resolution={"answer": "Yes"}, notes="done"),
    )
    assert resolved.status == "completed"
    assert resolved.resolution["answer"] == "Yes"
    session.refresh(run)
    assert run.metadata_json["paused"] is False
