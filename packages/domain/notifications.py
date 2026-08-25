"""NotificationService — in-app + email notifications with dedupe."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.models.enums import NotificationStatus
from database.models.schema import Notification
from packages.domain.events import UserEventPublisher, UserEventType
from packages.domain.exceptions import NotFoundError
from packages.domain.preferences import PreferencesService
from packages.providers.email_sender import EmailSendRequest, EmailSenderProvider
from packages.providers.notification import (
    NotificationChannel,
    NotificationProvider,
    NotificationSendRequest,
)


class NotificationType(StrEnum):
    application_submitted = "application_submitted"
    application_failed = "application_failed"
    human_action_required = "human_action_required"
    recruiter_response = "recruiter_response"
    referral_response = "referral_response"
    interview_scheduled = "interview_scheduled"
    followup_due = "followup_due"
    high_priority_job = "high_priority_job"
    workflow_failure = "workflow_failure"


class NotificationCreate(BaseModel):
    notification_type: NotificationType
    title: str = Field(min_length=1)
    body: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    dedupe_key: str | None = None
    send_email: bool = True


class NotificationView(BaseModel):
    id: uuid.UUID
    notification_type: str | None
    title: str | None
    body: str | None
    status: str
    data: dict[str, Any] = Field(default_factory=dict)
    dedupe_key: str | None = None
    created_at: datetime | None = None
    email_sent: bool = False
    duplicated: bool = False


class NotificationService:
    """Persist notifications with tenant isolation and optional email delivery."""

    def __init__(
        self,
        session: Session,
        user_id: uuid.UUID,
        *,
        email_sender: EmailSenderProvider | None = None,
        push_provider: NotificationProvider | None = None,
        events: UserEventPublisher | None = None,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._email_sender = email_sender
        self._push = push_provider
        self._events = events

    def list_notifications(
        self,
        *,
        status: NotificationStatus | None = NotificationStatus.unread,
        limit: int = 50,
    ) -> list[NotificationView]:
        q = self._session.query(Notification).filter(
            Notification.user_id == self._user_id
        )
        if status is not None:
            q = q.filter(Notification.status == status)
        rows = q.order_by(Notification.created_at.desc()).limit(limit).all()
        return [self._to_view(r) for r in rows]

    def create(self, payload: NotificationCreate) -> NotificationView:
        if payload.dedupe_key:
            existing = (
                self._session.query(Notification)
                .filter(
                    Notification.user_id == self._user_id,
                    Notification.dedupe_key == payload.dedupe_key,
                )
                .one_or_none()
            )
            if existing is not None:
                view = self._to_view(existing)
                view.duplicated = True
                return view

        row = Notification(
            id=uuid.uuid4(),
            user_id=self._user_id,
            status=NotificationStatus.unread,
            notification_type=payload.notification_type.value,
            title=payload.title,
            body=payload.body,
            data=payload.data or {},
            dedupe_key=payload.dedupe_key,
        )
        self._session.add(row)
        self._session.flush()

        email_sent = False
        if payload.send_email and self._email_sender is not None:
            email_sent = self._maybe_email(payload)

        if self._push is not None:
            self._push.send(
                NotificationSendRequest(
                    user_id=self._user_id,
                    channel=NotificationChannel.in_app,
                    title=payload.title,
                    body=payload.body,
                    payload={
                        "notification_id": str(row.id),
                        "type": payload.notification_type.value,
                        **(payload.data or {}),
                    },
                )
            )

        self._session.commit()
        self._session.refresh(row)

        if self._events is not None:
            self._events.publish(
                self._user_id,
                UserEventType.notification_created,
                {
                    "notification_id": str(row.id),
                    "type": payload.notification_type.value,
                },
            )

        view = self._to_view(row)
        view.email_sent = email_sent
        return view

    def mark_read(self, notification_id: uuid.UUID) -> NotificationView:
        row = self._get(notification_id)
        row.status = NotificationStatus.read
        self._session.commit()
        self._session.refresh(row)
        return self._to_view(row)

    def mark_all_read(self) -> int:
        rows = (
            self._session.query(Notification)
            .filter(
                Notification.user_id == self._user_id,
                Notification.status == NotificationStatus.unread,
            )
            .all()
        )
        for row in rows:
            row.status = NotificationStatus.read
        self._session.commit()
        return len(rows)

    def _get(self, notification_id: uuid.UUID) -> Notification:
        row = (
            self._session.query(Notification)
            .filter(
                Notification.id == notification_id,
                Notification.user_id == self._user_id,
            )
            .one_or_none()
        )
        if row is None:
            raise NotFoundError("Notification not found")
        return row

    def _maybe_email(self, payload: NotificationCreate) -> bool:
        assert self._email_sender is not None
        prefs = PreferencesService(self._session, self._user_id).get_settings()
        if not prefs.email_notifications_enabled:
            return False
        to_email = (prefs.notification_email or "").strip().lower()
        if not to_email or "@" not in to_email:
            # Never invent an email address.
            return False
        self._email_sender.send_email(
            EmailSendRequest(
                to=[to_email],
                subject=payload.title,
                body_text=payload.body or payload.title,
            )
        )
        return True

    @staticmethod
    def _to_view(row: Notification) -> NotificationView:
        data = row.data if isinstance(row.data, dict) else {}
        return NotificationView(
            id=row.id,
            notification_type=row.notification_type,
            title=row.title,
            body=row.body,
            status=row.status.value if hasattr(row.status, "value") else str(row.status),
            data=data,
            dedupe_key=row.dedupe_key,
            created_at=row.created_at,
        )
