"""Workflow progress persistence, ETA formatting, completion notifications."""

from __future__ import annotations

import uuid

import pytest

from database.models.enums import UserStatus, WorkflowRunStatus
from database.models.schema import User, WorkflowProgressEvent, WorkflowRun
from packages.domain.notifications import NotificationService
from packages.domain.preferences import PreferenceSettings, PreferencesService
from packages.domain.workflow_progress import (
    WorkflowProgressService,
    format_eta_remaining,
)
from packages.providers.email_sender import MockEmailSenderProvider


def _session():
    from app.database import get_session_factory

    return get_session_factory()()


def _ensure_user(session, subject: str = "supabase-user-a") -> User:
    user = session.query(User).filter(User.auth_subject == subject).one_or_none()
    if user is None:
        user = User(id=uuid.uuid4(), auth_subject=subject, status=UserStatus.active)
        session.add(user)
        session.commit()
    return user


def test_format_eta_remaining_rounds_minutes():
    assert format_eta_remaining(30_000) == "Less than a minute left"
    assert format_eta_remaining(90_000).startswith("About 2 minute")
    assert format_eta_remaining(None) == "Calculating time left…"


@pytest.mark.skip(reason="Requires Postgres with workflow_progress_events migration applied")
def test_record_progress_persists_and_updates_metadata(auth_client):
    session = _session()
    user = _ensure_user(session)
    run = WorkflowRun(
        id=uuid.uuid4(),
        user_id=user.id,
        status=WorkflowRunStatus.running,
        workflow_type="job_discovery",
        metadata_json={},
    )
    session.add(run)
    session.commit()

    svc = WorkflowProgressService(session, user.id)
    svc.seed_eta(run, planned_units=10)
    evt = svc.record_progress(
        run,
        step="search",
        message='Searched “software engineer remote” — 8 listings',
        phase="result",
        display={"query_label": "software engineer remote", "count": 8},
        completed_units=1,
        planned_units=10,
    )
    session.commit()

    rows = (
        session.query(WorkflowProgressEvent)
        .filter_by(workflow_run_id=run.id)
        .all()
    )
    assert len(rows) == 1
    assert rows[0].message.startswith("Searched")
    assert rows[0].id == evt.id
    meta = dict(run.metadata_json or {})
    assert meta.get("status_message", "").startswith("Searched")
    assert meta.get("planned_units") == 10
    assert meta.get("completed_units") == 1
    assert 0 < float(meta.get("progress_ratio", 0)) <= 1
    assert meta.get("estimated_duration_ms")


@pytest.mark.skip(reason="Requires Postgres with workflow_progress_events migration applied")
def test_notify_terminal_creates_in_app_and_email(auth_client):
    session = _session()
    user = _ensure_user(session)
    PreferencesService(session, user.id).update(
        PreferenceSettings(
            email_notifications_enabled=True,
            notification_email="user@example.com",
        )
    )
    run = WorkflowRun(
        id=uuid.uuid4(),
        user_id=user.id,
        status=WorkflowRunStatus.completed,
        workflow_type="job_discovery",
        metadata_json={"created_jobs": 3},
    )
    session.add(run)
    session.commit()

    sender = MockEmailSenderProvider()
    notif = NotificationService(session, user.id, email_sender=sender)
    svc = WorkflowProgressService(session, user.id, notifications=notif)
    svc.notify_terminal(
        run,
        status="completed",
        title="Job discovery finished",
        body="Found 3 new jobs. Open Activity for details.",
    )
    session.commit()

    assert len(sender.sent) == 1
    svc.notify_terminal(
        run,
        status="completed",
        title="Job discovery finished",
        body="Found 3 new jobs. Open Activity for details.",
    )
    assert len(sender.sent) == 1
