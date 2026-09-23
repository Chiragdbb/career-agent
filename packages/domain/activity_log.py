"""Persisted activity log from workflow runs and progress events."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from database.models.schema import WorkflowProgressEvent, WorkflowRun
from packages.domain.workflow_progress import format_eta_remaining


@dataclass(frozen=True)
class ActivityStep:
    id: str
    timestamp: datetime
    step: str
    phase: str
    message: str
    display: dict | None


@dataclass(frozen=True)
class ActivityRun:
    id: uuid.UUID
    workflow_type: str
    status: str
    message: str
    human_title: str | None
    metadata: dict | None
    created_at: datetime | None
    updated_at: datetime | None
    error: str | None
    eta_label: str | None
    steps: list[ActivityStep] = field(default_factory=list)


# Backward-compatible flat entry used by older clients
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

    def list_runs(
        self,
        *,
        before: datetime | None = None,
        limit: int = 50,
    ) -> list[ActivityRun]:
        limit = max(1, min(limit, 100))
        q = self._session.query(WorkflowRun).filter(WorkflowRun.user_id == self._user_id)
        if before is not None:
            q = q.filter(WorkflowRun.created_at < before)
        runs = q.order_by(WorkflowRun.created_at.desc()).limit(limit).all()
        if not runs:
            return []

        run_ids = [r.id for r in runs]
        events = (
            self._session.query(WorkflowProgressEvent)
            .filter(
                WorkflowProgressEvent.user_id == self._user_id,
                WorkflowProgressEvent.workflow_run_id.in_(run_ids),
            )
            .order_by(WorkflowProgressEvent.created_at.asc())
            .all()
        )
        by_run: dict[uuid.UUID, list[ActivityStep]] = {rid: [] for rid in run_ids}
        for ev in events:
            by_run.setdefault(ev.workflow_run_id, []).append(
                ActivityStep(
                    id=str(ev.id),
                    timestamp=ev.created_at or datetime.min,
                    step=ev.step,
                    phase=ev.phase,
                    message=ev.message,
                    display=ev.display if isinstance(ev.display, dict) else None,
                )
            )

        out: list[ActivityRun] = []
        for run in runs:
            meta = run.metadata_json if isinstance(run.metadata_json, dict) else {}
            message = meta.get("status_message") or f"Workflow {run.workflow_type} {run.status.value}"
            remaining = meta.get("eta_remaining_ms")
            eta = None
            if run.status.value in {"queued", "running", "cancelling"}:
                eta = format_eta_remaining(
                    int(remaining) if isinstance(remaining, (int, float)) else None
                )
            out.append(
                ActivityRun(
                    id=run.id,
                    workflow_type=run.workflow_type,
                    status=run.status.value,
                    message=str(message),
                    human_title=str(meta["human_title"]) if meta.get("human_title") else None,
                    metadata=meta,
                    created_at=run.created_at,
                    updated_at=run.updated_at,
                    error=run.error,
                    eta_label=eta,
                    steps=by_run.get(run.id, []),
                )
            )
        return out

    def list_entries(
        self,
        *,
        before: datetime | None = None,
        limit: int = 50,
    ) -> list[ActivityEntry]:
        """Legacy flat list (run summary rows only). Prefer list_runs."""
        runs = self.list_runs(before=before, limit=limit)
        entries: list[ActivityEntry] = []
        for run in reversed(runs):
            entries.append(
                ActivityEntry(
                    id=f"run-{run.id}",
                    timestamp=run.created_at or datetime.min,
                    entry_type="workflow_run",
                    message=run.message,
                    workflow_run_id=run.id,
                    workflow_type=run.workflow_type,
                    metadata={
                        "status": run.status,
                        "error": run.error,
                        **(run.metadata or {}),
                    },
                )
            )
        return entries
