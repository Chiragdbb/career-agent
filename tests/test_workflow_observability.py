"""Tests for workflow observability service and API."""

from __future__ import annotations

import uuid

import pytest

from database.models.enums import UserStatus, WorkflowRunStatus, WorkflowTaskStatus
from database.models.schema import User, WorkflowRun, WorkflowTask
from packages.domain.workflows import WorkflowObservabilityService


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


@pytest.fixture
def workflow_fixture():
    session = _session()
    user = _ensure_user(session)
    run = WorkflowRun(
        id=uuid.uuid4(),
        user_id=user.id,
        status=WorkflowRunStatus.running,
        workflow_type="job_discovery",
        metadata_json={"current_step": "search", "status_message": "Searching"},
    )
    session.add(run)
    session.flush()
    task = WorkflowTask(
        id=uuid.uuid4(),
        user_id=user.id,
        workflow_run_id=run.id,
        status=WorkflowTaskStatus.completed,
        task_type="search",
        input_payload={"query": "engineer jobs remote"},
        output_payload={"urls": ["https://example.test/job"]},
        attempt=1,
    )
    session.add(task)
    session.commit()
    try:
        yield {"user_id": user.id, "run_id": run.id, "task_id": task.id}
    finally:
        session.query(WorkflowTask).filter(WorkflowTask.user_id == user.id).delete()
        session.query(WorkflowRun).filter(WorkflowRun.user_id == user.id).delete()
        session.commit()
        session.close()


def test_list_workflow_runs(auth_client, workflow_fixture) -> None:
    response = auth_client.get(
        "/api/v1/workflows",
        headers={"Authorization": "Bearer token-user-a"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)


def test_get_workflow_run_and_tasks(auth_client, workflow_fixture) -> None:
    run_id = workflow_fixture["run_id"]
    run_response = auth_client.get(
        f"/api/v1/workflows/{run_id}",
        headers={"Authorization": "Bearer token-user-a"},
    )
    assert run_response.status_code == 200
    run_data = run_response.json()
    assert run_data["workflow_type"] == "job_discovery"
    assert run_data["status"] == "running"
    assert run_data["task_count"] == 1
    assert run_data["completed_task_count"] == 1

    tasks_response = auth_client.get(
        f"/api/v1/workflows/{run_id}/tasks",
        headers={"Authorization": "Bearer token-user-a"},
    )
    assert tasks_response.status_code == 200
    tasks = tasks_response.json()
    assert len(tasks) == 1
    assert tasks[0]["task_type"] == "search"
    assert tasks[0]["input_payload"]["query"] == "engineer jobs remote"


def test_cancel_workflow_run(auth_client, workflow_fixture) -> None:
    run_id = workflow_fixture["run_id"]
    response = auth_client.post(
        f"/api/v1/workflows/{run_id}/cancel",
        headers={"Authorization": "Bearer token-user-a"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cancelled"
    assert data["metadata"]["current_step"] == "cancelled"


def test_cancel_completed_workflow_returns_error(auth_client, workflow_fixture) -> None:
    session = _session()
    run = session.query(WorkflowRun).filter(WorkflowRun.id == workflow_fixture["run_id"]).one()
    run.status = WorkflowRunStatus.completed
    session.commit()
    session.close()

    response = auth_client.post(
        f"/api/v1/workflows/{workflow_fixture['run_id']}/cancel",
        headers={"Authorization": "Bearer token-user-a"},
    )
    assert response.status_code == 400


def test_workflow_observability_service_tenant_isolation(workflow_fixture) -> None:
    session = _session()
    other_user = _ensure_user(session, subject="other-workflow-user")
    service = WorkflowObservabilityService(session, other_user.id)
    runs = service.list_runs()
    run_ids = {str(r.id) for r in runs}
    assert str(workflow_fixture["run_id"]) not in run_ids
    session.close()
