"""Tenant-scoped workflow run and task observability."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from database.models.enums import WorkflowRunStatus
from database.models.schema import WorkflowRun, WorkflowTask
from packages.domain.exceptions import NotFoundError


@dataclass(frozen=True)
class WorkflowRunSummary:
    id: uuid.UUID
    workflow_type: str
    status: str
    error: str | None
    metadata: dict | None
    created_at: datetime | None
    updated_at: datetime | None
    task_count: int
    completed_task_count: int
    failed_task_count: int


@dataclass(frozen=True)
class WorkflowTaskSummary:
    id: uuid.UUID
    workflow_run_id: uuid.UUID
    task_type: str
    status: str
    input_payload: dict | None
    output_payload: dict | None
    error: str | None
    attempt: int | None
    created_at: datetime | None
    updated_at: datetime | None


class WorkflowObservabilityService:
    """Read workflow runs and step-level task logs for one tenant."""

    TERMINAL_STATUSES = (
        WorkflowRunStatus.completed,
        WorkflowRunStatus.failed,
        WorkflowRunStatus.cancelled,
    )

    def __init__(self, session: Session, user_id: uuid.UUID) -> None:
        self._session = session
        self._user_id = user_id

    def list_runs(
        self,
        *,
        limit: int = 20,
        active_only: bool = False,
    ) -> list[WorkflowRunSummary]:
        query = self._session.query(WorkflowRun).filter(WorkflowRun.user_id == self._user_id)
        if active_only:
            query = query.filter(
                WorkflowRun.status.in_(
                    (WorkflowRunStatus.queued, WorkflowRunStatus.running)
                )
            )
        rows = query.order_by(WorkflowRun.created_at.desc()).limit(limit).all()
        return [self._to_run_summary(row) for row in rows]

    def get_run(self, run_id: uuid.UUID) -> WorkflowRunSummary:
        row = (
            self._session.query(WorkflowRun)
            .filter(WorkflowRun.id == run_id, WorkflowRun.user_id == self._user_id)
            .one_or_none()
        )
        if row is None:
            raise NotFoundError("Workflow run not found")
        return self._to_run_summary(row)

    def list_tasks(self, run_id: uuid.UUID) -> list[WorkflowTaskSummary]:
        run = (
            self._session.query(WorkflowRun)
            .filter(WorkflowRun.id == run_id, WorkflowRun.user_id == self._user_id)
            .one_or_none()
        )
        if run is None:
            raise NotFoundError("Workflow run not found")
        rows = (
            self._session.query(WorkflowTask)
            .filter(
                WorkflowTask.workflow_run_id == run_id,
                WorkflowTask.user_id == self._user_id,
            )
            .order_by(WorkflowTask.created_at.asc())
            .all()
        )
        return [self._to_task_summary(row) for row in rows]

    def _to_run_summary(self, row: WorkflowRun) -> WorkflowRunSummary:
        tasks = (
            self._session.query(WorkflowTask)
            .filter(
                WorkflowTask.workflow_run_id == row.id,
                WorkflowTask.user_id == self._user_id,
            )
            .all()
        )
        completed = sum(1 for t in tasks if _status_value(t.status) == "completed")
        failed = sum(1 for t in tasks if _status_value(t.status) == "failed")
        return WorkflowRunSummary(
            id=row.id,
            workflow_type=row.workflow_type,
            status=_status_value(row.status),
            error=row.error,
            metadata=row.metadata_json if isinstance(row.metadata_json, dict) else None,
            created_at=row.created_at,
            updated_at=row.updated_at,
            task_count=len(tasks),
            completed_task_count=completed,
            failed_task_count=failed,
        )

    @staticmethod
    def _to_task_summary(row: WorkflowTask) -> WorkflowTaskSummary:
        return WorkflowTaskSummary(
            id=row.id,
            workflow_run_id=row.workflow_run_id,
            task_type=row.task_type,
            status=_status_value(row.status),
            input_payload=row.input_payload if isinstance(row.input_payload, dict) else None,
            output_payload=row.output_payload if isinstance(row.output_payload, dict) else None,
            error=row.error,
            attempt=row.attempt,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


def _status_value(status: object) -> str:
    return status.value if hasattr(status, "value") else str(status)
