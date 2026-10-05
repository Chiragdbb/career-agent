"""Durable human-readable workflow progress + ETA + terminal notifications."""

from __future__ import annotations

import statistics
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from database.models.enums import WorkflowRunStatus
from database.models.schema import WorkflowProgressEvent, WorkflowRun
from packages.domain.events import UserEventPublisher, UserEventType
from packages.domain.notifications import (
    NotificationCreate,
    NotificationService,
    NotificationType,
)

_BASELINE_MS = {
    "job_discovery": 180_000,
    "job_rescrape": 90_000,
    "career_job_pipeline": 240_000,
}
_PER_UNIT_MS = {
    "job_discovery": 25_000,
    "job_rescrape": 60_000,
    "career_job_pipeline": 25_000,
}


def format_eta_remaining(remaining_ms: int | None) -> str:
    if remaining_ms is None:
        return "Calculating time left…"
    if remaining_ms < 90_000:
        return "Less than a minute left"
    minutes = max(1, int(round(remaining_ms / 60_000)))
    unit = "minute" if minutes == 1 else "minutes"
    return f"About {minutes} {unit} left"


def estimate_duration_ms(
    session: Session,
    user_id: uuid.UUID,
    workflow_type: str,
    *,
    planned_units: int,
) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    runs = (
        session.query(WorkflowRun)
        .filter(
            WorkflowRun.user_id == user_id,
            WorkflowRun.workflow_type == workflow_type,
            WorkflowRun.status == WorkflowRunStatus.completed,
            WorkflowRun.created_at >= cutoff,
            WorkflowRun.updated_at.isnot(None),
        )
        .order_by(WorkflowRun.created_at.desc())
        .limit(10)
        .all()
    )
    durations: list[float] = []
    for r in runs:
        if r.created_at and r.updated_at:
            durations.append((r.updated_at - r.created_at).total_seconds() * 1000)
    if len(durations) >= 3:
        return int(statistics.median(durations) * 1.1)
    base = _BASELINE_MS.get(workflow_type, 120_000)
    per = _PER_UNIT_MS.get(workflow_type, 20_000)
    return int(base + max(1, planned_units) * per)


class WorkflowProgressService:
    def __init__(
        self,
        session: Session,
        user_id: uuid.UUID,
        *,
        events: UserEventPublisher | None = None,
        notifications: NotificationService | None = None,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._events = events
        self._notifications = notifications

    def seed_eta(self, run: WorkflowRun, *, planned_units: int) -> None:
        meta = dict(run.metadata_json or {})
        prior_completed = int(meta.get("completed_units") or 0)
        prior_ratio = float(meta.get("progress_ratio") or 0.0)
        est = estimate_duration_ms(
            self._session,
            self._user_id,
            run.workflow_type,
            planned_units=planned_units,
        )
        now = datetime.now(timezone.utc)
        meta["planned_units"] = planned_units
        # Preserve progress when reseeding (resume / mid-run refresh) so the
        # single progress bar never restarts from zero for later steps.
        meta["completed_units"] = prior_completed
        meta["estimated_duration_ms"] = est
        started_raw = meta.get("pipeline_started_at")
        if not started_raw:
            meta["pipeline_started_at"] = now.isoformat()
            started_at = now
        else:
            try:
                started_at = datetime.fromisoformat(str(started_raw).replace("Z", "+00:00"))
            except ValueError:
                started_at = now
                meta["pipeline_started_at"] = now.isoformat()
        # Wall-clock deadline from original start — do not restart the timer on resume.
        meta["eta_deadline_at"] = (started_at + timedelta(milliseconds=est)).isoformat()
        if prior_completed > 0 and planned_units > 0:
            ratio = min(1.0, prior_completed / planned_units)
            meta["progress_ratio"] = max(prior_ratio, ratio)
        else:
            meta["progress_ratio"] = prior_ratio if prior_ratio > 0 else 0.0
        remaining = int(
            (
                datetime.fromisoformat(str(meta["eta_deadline_at"]).replace("Z", "+00:00"))
                - now
            ).total_seconds()
            * 1000
        )
        meta["eta_remaining_ms"] = max(0, remaining)
        run.metadata_json = meta
        self._session.flush()

    def record_progress(
        self,
        run: WorkflowRun,
        *,
        step: str,
        message: str,
        phase: str = "working",
        display: dict[str, Any] | None = None,
        completed_units: int | None = None,
        planned_units: int | None = None,
    ) -> WorkflowProgressEvent | None:
        meta = dict(run.metadata_json or {})
        if planned_units is not None:
            meta["planned_units"] = planned_units
        prior_completed = int(meta.get("completed_units") or 0)
        prior_ratio = float(meta.get("progress_ratio") or 0.0)
        if completed_units is not None:
            # Never let progress go backwards across steps.
            meta["completed_units"] = max(prior_completed, int(completed_units))
        planned = int(meta.get("planned_units") or 0)
        completed = int(meta.get("completed_units") or 0)
        if planned > 0:
            ratio = min(1.0, completed / planned)
            meta["progress_ratio"] = max(prior_ratio, ratio)
            est = int(meta.get("estimated_duration_ms") or 0)
            deadline_raw = meta.get("eta_deadline_at")
            if deadline_raw:
                try:
                    deadline = datetime.fromisoformat(
                        str(deadline_raw).replace("Z", "+00:00")
                    )
                    remaining = int(
                        (deadline - datetime.now(timezone.utc)).total_seconds() * 1000
                    )
                    meta["eta_remaining_ms"] = max(0, remaining)
                except ValueError:
                    meta["eta_remaining_ms"] = max(
                        0, int((1.0 - meta["progress_ratio"]) * est)
                    )
            else:
                meta["eta_remaining_ms"] = max(
                    0, int((1.0 - meta["progress_ratio"]) * est)
                )
        meta["current_step"] = step
        meta["status_message"] = message
        run.metadata_json = meta

        row = WorkflowProgressEvent(
            id=uuid.uuid4(),
            user_id=self._user_id,
            workflow_run_id=run.id,
            workflow_type=run.workflow_type,
            step=step,
            phase=phase,
            message=message,
            display=display or {},
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
        except Exception:
            # Migrations may lag behind code; never block the workflow on progress rows.
            row = None

        if self._events is not None:
            try:
                self._events.publish(
                    self._user_id,
                    UserEventType.workflow_progress,
                    {
                        "workflow_run_id": str(run.id),
                        "workflow_type": run.workflow_type,
                        "step": step,
                        "phase": phase,
                        "message": message,
                        "data": {
                            **(display or {}),
                            "phase": phase,
                            "progress_ratio": meta.get("progress_ratio"),
                            "eta_remaining_ms": meta.get("eta_remaining_ms"),
                            "estimated_duration_ms": meta.get("estimated_duration_ms"),
                        },
                    },
                )
            except Exception:
                pass
        return row

    def list_for_run(self, run_id: uuid.UUID) -> list[WorkflowProgressEvent]:
        return (
            self._session.query(WorkflowProgressEvent)
            .filter(
                WorkflowProgressEvent.user_id == self._user_id,
                WorkflowProgressEvent.workflow_run_id == run_id,
            )
            .order_by(WorkflowProgressEvent.created_at.asc())
            .all()
        )

    def notify_terminal(
        self,
        run: WorkflowRun,
        *,
        status: str,
        title: str,
        body: str,
    ) -> None:
        if self._notifications is None:
            return
        ntype = (
            NotificationType.workflow_failure
            if status == "failed"
            else NotificationType.workflow_completed
        )
        self._notifications.create(
            NotificationCreate(
                notification_type=ntype,
                title=title,
                body=body,
                data={
                    "workflow_run_id": str(run.id),
                    "workflow_type": run.workflow_type,
                    "status": status,
                },
                dedupe_key=f"workflow-{run.id}-{status}",
                send_email=True,
            )
        )
