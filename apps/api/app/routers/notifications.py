"""Notifications API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.dependencies import CurrentUserIdDep, DbSessionDep, EventPublisherDep
from app.schemas.saas import NotificationResponse
from database.models.enums import NotificationStatus
from packages.domain.notifications import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _service(session, user_id, events=None) -> NotificationService:
    # List/mark-read do not need email sender — avoid constructing it.
    return NotificationService(session, user_id, email_sender=None, events=events)


@router.get("", response_model=list[NotificationResponse])
def list_notifications(
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
    events: EventPublisherDep,
    status: str | None = Query(default="unread"),
) -> list[NotificationResponse]:
    status_enum: NotificationStatus | None = None
    if status:
        status_enum = NotificationStatus(status)
    rows = _service(session, user_id, events).list_notifications(status=status_enum)
    return [NotificationResponse(**r.model_dump()) for r in rows]


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: UUID,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
    events: EventPublisherDep,
) -> NotificationResponse:
    view = _service(session, user_id, events).mark_read(notification_id)
    return NotificationResponse(**view.model_dump())


@router.post("/read-all")
def mark_all_read(
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
    events: EventPublisherDep,
) -> dict:
    count = _service(session, user_id, events).mark_all_read()
    return {"updated": count}
