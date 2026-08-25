"""HumanTaskService — pause workflows for human action, notify, resume on resolve."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.models.enums import HumanTaskStatus, NotificationStatus
from database.models.schema import HumanTask, Notification, WorkflowRun
from packages.domain.exceptions import DomainError, NotFoundError
from packages.providers.notification import (
    NotificationChannel,
    NotificationProvider,
    NotificationSendRequest,
)


class HumanTaskType(StrEnum):
    unknown_question = "unknown_question"
    captcha = "captcha"
    login_required = "login_required"
    ambiguous_field = "ambiguous_field"
    missing_candidate_info = "missing_candidate_info"
    approval_required_outreach = "approval_required_outreach"
    approval_required_application = "approval_required_application"


class HumanTaskCreate(BaseModel):
    task_type: HumanTaskType
    title: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)
    blocking_entity_type: str | None = None
    blocking_entity_id: uuid.UUID | None = None
    application_id: uuid.UUID | None = None
    outreach_id: uuid.UUID | None = None
    workflow_run_id: uuid.UUID | None = None
    notify: bool = True


class HumanTaskView(BaseModel):
    id: uuid.UUID
    task_type: str
    title: str | None
    status: str
    details: dict[str, Any] = Field(default_factory=dict)
    blocking_entity_type: str | None = None
    blocking_entity_id: uuid.UUID | None = None
    application_id: uuid.UUID | None = None
    outreach_id: uuid.UUID | None = None
    workflow_run_id: uuid.UUID | None = None
    resolution: dict[str, Any] | None = None
    created_at: datetime | None = None


class HumanTaskResolveInput(BaseModel):
    resolution: dict[str, Any] = Field(default_factory=dict)
    resume_workflow: bool = True
    notes: str | None = None


class HumanTaskService:
    """Create / list / resolve human tasks; pause+resume linked workflows."""

    def __init__(
        self,
        session: Session,
        user_id: uuid.UUID,
        *,
        notifications: NotificationProvider | None = None,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._notifications = notifications

    def create(self, payload: HumanTaskCreate) -> HumanTaskView:
        task = HumanTask(
            id=uuid.uuid4(),
            user_id=self._user_id,
            status=HumanTaskStatus.open,
            task_type=payload.task_type.value,
            title=payload.title,
            details=dict(payload.details),
            blocking_entity_type=payload.blocking_entity_type,
            blocking_entity_id=payload.blocking_entity_id,
            application_id=payload.application_id,
            outreach_id=payload.outreach_id,
            workflow_run_id=payload.workflow_run_id,
        )
        self._session.add(task)

        if payload.workflow_run_id is not None:
            self._pause_workflow(payload.workflow_run_id, task_id=task.id)

        self._session.flush()

        if payload.notify and self._notifications is not None:
            notif_resp = self._notifications.send(
                NotificationSendRequest(
                    user_id=self._user_id,
                    channel=NotificationChannel.in_app,
                    title=f"Action required: {payload.title}",
                    body=f"Human task ({payload.task_type.value}) needs your attention.",
                    payload={
                        "human_task_id": str(task.id),
                        "task_type": payload.task_type.value,
                    },
                )
            )
            row = Notification(
                id=uuid.uuid4(),
                user_id=self._user_id,
                status=NotificationStatus.unread,
                notification_type="human_task",
                title=f"Action required: {payload.title}",
                body=f"Human task ({payload.task_type.value}) needs your attention.",
                data={
                    "human_task_id": str(task.id),
                    "provider_notification_id": notif_resp.notification_id,
                },
            )
            self._session.add(row)

        self._session.commit()
        self._session.refresh(task)
        return self._to_view(task)

    def list_tasks(
        self,
        *,
        status: HumanTaskStatus | None = HumanTaskStatus.open,
        limit: int = 50,
    ) -> list[HumanTaskView]:
        q = self._session.query(HumanTask).filter(HumanTask.user_id == self._user_id)
        if status is not None:
            q = q.filter(HumanTask.status == status)
        rows = q.order_by(HumanTask.created_at.desc()).limit(limit).all()
        return [self._to_view(r) for r in rows]

    def get(self, task_id: uuid.UUID) -> HumanTaskView:
        return self._to_view(self._get(task_id))

    def resolve(self, task_id: uuid.UUID, payload: HumanTaskResolveInput) -> HumanTaskView:
        task = self._get(task_id)
        if task.status in (HumanTaskStatus.completed, HumanTaskStatus.cancelled):
            raise DomainError(f"Human task already {task.status.value}")

        details = dict(task.details or {})
        details["resolution"] = {
            **payload.resolution,
            "notes": payload.notes,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
        }
        task.details = details
        task.status = HumanTaskStatus.completed

        if payload.resume_workflow and task.workflow_run_id is not None:
            self._resume_workflow(task.workflow_run_id, task_id=task.id)

        self._session.commit()
        self._session.refresh(task)
        return self._to_view(task)

    def _get(self, task_id: uuid.UUID) -> HumanTask:
        row = (
            self._session.query(HumanTask)
            .filter(HumanTask.id == task_id, HumanTask.user_id == self._user_id)
            .one_or_none()
        )
        if row is None:
            raise NotFoundError("Human task not found")
        return row

    def _pause_workflow(self, workflow_run_id: uuid.UUID, *, task_id: uuid.UUID) -> None:
        run = (
            self._session.query(WorkflowRun)
            .filter(
                WorkflowRun.id == workflow_run_id,
                WorkflowRun.user_id == self._user_id,
            )
            .one_or_none()
        )
        if run is None:
            return
        meta = dict(run.metadata_json or {})
        meta["paused"] = True
        meta["paused_at"] = datetime.now(timezone.utc).isoformat()
        meta["pause_human_task_id"] = str(task_id)
        run.metadata_json = meta

    def _resume_workflow(self, workflow_run_id: uuid.UUID, *, task_id: uuid.UUID) -> None:
        run = (
            self._session.query(WorkflowRun)
            .filter(
                WorkflowRun.id == workflow_run_id,
                WorkflowRun.user_id == self._user_id,
            )
            .one_or_none()
        )
        if run is None:
            return
        meta = dict(run.metadata_json or {})
        meta["paused"] = False
        meta["resumed_at"] = datetime.now(timezone.utc).isoformat()
        meta["resume_human_task_id"] = str(task_id)
        # Keep a trail of pauses.
        history = list(meta.get("pause_history") or [])
        history.append(
            {
                "task_id": str(task_id),
                "resumed_at": meta["resumed_at"],
            }
        )
        meta["pause_history"] = history
        run.metadata_json = meta

    @staticmethod
    def _to_view(task: HumanTask) -> HumanTaskView:
        details = task.details if isinstance(task.details, dict) else {}
        resolution = details.get("resolution") if isinstance(details, dict) else None
        return HumanTaskView(
            id=task.id,
            task_type=task.task_type,
            title=task.title,
            status=task.status.value if hasattr(task.status, "value") else str(task.status),
            details=details,
            blocking_entity_type=task.blocking_entity_type,
            blocking_entity_id=task.blocking_entity_id,
            application_id=task.application_id,
            outreach_id=task.outreach_id,
            workflow_run_id=task.workflow_run_id,
            resolution=resolution if isinstance(resolution, dict) else None,
            created_at=getattr(task, "created_at", None),
        )
