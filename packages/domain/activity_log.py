"""Persisted activity log from workflow runs and tasks."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from database.models.schema import WorkflowRun, WorkflowTask


@dataclass(frozen=True)
class ActivityEntry:
    id: str
    timestamp: datetime
    entry_type: str
    message: str
    workflow_run_id: uuid.UUID | None
    workflow_type: str | None
    metadata: dict | None


class ActivityLogService:
    def __init__(self, session: Session, user_id: uuid.UUID) -> None:
        self._session = session
        self._user_id = user_id

    def list_entries(
        self,
        *,
        before: datetime | None = None,
        limit: int = 50,
    ) -> list[ActivityEntry]:
        limit = max(1, min(limit, 100))
        run_query = self._session.query(WorkflowRun).filter(WorkflowRun.user_id == self._user_id)
        task_query = (
            self._session.query(WorkflowTask)
            .filter(WorkflowTask.user_id == self._user_id)
        )
        if before is not None:
            run_query = run_query.filter(WorkflowRun.created_at < before)
            task_query = task_query.filter(WorkflowTask.created_at < before)

        runs = run_query.order_by(WorkflowRun.created_at.desc()).limit(limit).all()
        run_ids = [r.id for r in runs]
        tasks = (
            task_query.filter(WorkflowTask.workflow_run_id.in_(run_ids))
            .order_by(WorkflowTask.created_at.desc())
            .all()
            if run_ids
            else []
        )

        entries: list[ActivityEntry] = []
        for run in runs:
            meta = run.metadata_json if isinstance(run.metadata_json, dict) else {}
            message = meta.get("status_message") or f"Workflow {run.workflow_type} {run.status.value}"
            entries.append(
                ActivityEntry(
                    id=f"run-{run.id}",
                    timestamp=run.created_at or datetime.min,
                    entry_type="workflow_run",
                    message=message,
                    workflow_run_id=run.id,
                    workflow_type=run.workflow_type,
                    metadata={
                        "status": run.status.value,
                        "error": run.error,
                        **meta,
                    },
                )
            )
        for task in tasks:
            entries.append(
                ActivityEntry(
                    id=f"task-{task.id}",
                    timestamp=task.created_at or datetime.min,
                    entry_type="workflow_task",
                    message=f"{task.task_type} — {task.status.value}",
                    workflow_run_id=task.workflow_run_id,
                    workflow_type=None,
                    metadata={
                        "task_type": task.task_type,
                        "status": task.status.value,
                        "input": task.input_payload,
                        "output": task.output_payload,
                        "error": task.error,
                    },
                )
            )

        entries.sort(key=lambda e: e.timestamp)
        if len(entries) > limit:
            entries = entries[-limit:]
        return entries
