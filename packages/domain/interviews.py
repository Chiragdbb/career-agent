"""Interview and Offer tracking services (tenant-scoped)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.models.enums import InterviewStatus, OfferStatus
from database.models.schema import Application, ApplicationEvent, Interview, Offer
from packages.domain.events import UserEventPublisher, UserEventType
from packages.domain.exceptions import NotFoundError
from packages.domain.notifications import (
    NotificationCreate,
    NotificationService,
    NotificationType,
)


class InterviewCreate(BaseModel):
    application_id: uuid.UUID
    title: str | None = None
    scheduled_at: datetime | None = None
    notes: str | None = None
    round: int | None = Field(default=None, ge=1, le=20)
    format: str | None = None
    interviewer: str | None = None
    status: InterviewStatus = InterviewStatus.scheduled


class InterviewUpdate(BaseModel):
    title: str | None = None
    scheduled_at: datetime | None = None
    notes: str | None = None
    round: int | None = Field(default=None, ge=1, le=20)
    format: str | None = None
    interviewer: str | None = None
    status: InterviewStatus | None = None


class InterviewView(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    status: str
    title: str | None = None
    scheduled_at: datetime | None = None
    notes: str | None = None
    round: int | None = None
    format: str | None = None
    interviewer: str | None = None


class OfferCreate(BaseModel):
    application_id: uuid.UUID
    compensation: str | None = None
    equity: str | None = None
    location: str | None = None
    deadline: datetime | None = None
    status: OfferStatus = OfferStatus.pending
    details: dict[str, Any] = Field(default_factory=dict)


class OfferUpdate(BaseModel):
    compensation: str | None = None
    equity: str | None = None
    location: str | None = None
    deadline: datetime | None = None
    status: OfferStatus | None = None
    details: dict[str, Any] | None = None


class OfferView(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    status: str
    offer_deadline: datetime | None = None
    compensation: str | None = None
    equity: str | None = None
    location: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class InterviewService:
    def __init__(
        self,
        session: Session,
        user_id: uuid.UUID,
        *,
        events: UserEventPublisher | None = None,
        notification_service: NotificationService | None = None,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._events = events
        self._notification_service = notification_service

    def list_interviews(
        self, *, application_id: uuid.UUID | None = None
    ) -> list[InterviewView]:
        q = self._session.query(Interview).filter(Interview.user_id == self._user_id)
        if application_id is not None:
            q = q.filter(Interview.application_id == application_id)
        rows = q.order_by(Interview.scheduled_at.desc().nullslast()).all()
        return [self._to_view(r) for r in rows]

    def get(self, interview_id: uuid.UUID) -> InterviewView:
        return self._to_view(self._get(interview_id))

    def create(self, payload: InterviewCreate) -> InterviewView:
        self._get_application(payload.application_id)
        row = Interview(
            id=uuid.uuid4(),
            user_id=self._user_id,
            application_id=payload.application_id,
            status=payload.status,
            title=payload.title,
            scheduled_at=payload.scheduled_at,
            notes=payload.notes,
            round=payload.round,
            format=payload.format,
            interviewer=payload.interviewer,
        )
        self._session.add(row)
        self._append_event(
            payload.application_id,
            "interview_scheduled",
            {
                "interview_id": str(row.id),
                "round": payload.round,
                "scheduled_at": payload.scheduled_at.isoformat()
                if payload.scheduled_at
                else None,
            },
        )
        self._session.commit()
        self._session.refresh(row)

        if self._notification_service is not None:
            self._notification_service.create(
                NotificationCreate(
                    notification_type=NotificationType.interview_scheduled,
                    title=payload.title or "Interview scheduled",
                    body=payload.notes or "An interview was added to your pipeline.",
                    data={"interview_id": str(row.id)},
                    dedupe_key=f"interview:{row.id}",
                )
            )
        if self._events is not None:
            self._events.publish(
                self._user_id,
                UserEventType.interview_scheduled,
                {"interview_id": str(row.id), "application_id": str(payload.application_id)},
            )
        return self._to_view(row)

    def update(self, interview_id: uuid.UUID, payload: InterviewUpdate) -> InterviewView:
        row = self._get(interview_id)
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        self._append_event(
            row.application_id,
            "interview_updated",
            {"interview_id": str(row.id), **{k: str(v) if v is not None else None for k, v in data.items()}},
        )
        self._session.commit()
        self._session.refresh(row)
        return self._to_view(row)

    def _get(self, interview_id: uuid.UUID) -> Interview:
        row = (
            self._session.query(Interview)
            .filter(Interview.id == interview_id, Interview.user_id == self._user_id)
            .one_or_none()
        )
        if row is None:
            raise NotFoundError("Interview not found")
        return row

    def _get_application(self, application_id: uuid.UUID) -> Application:
        row = (
            self._session.query(Application)
            .filter(Application.id == application_id, Application.user_id == self._user_id)
            .one_or_none()
        )
        if row is None:
            raise NotFoundError("Application not found")
        return row

    def _append_event(
        self, application_id: uuid.UUID, event_type: str, payload: dict[str, Any]
    ) -> None:
        self._session.add(
            ApplicationEvent(
                id=uuid.uuid4(),
                user_id=self._user_id,
                application_id=application_id,
                event_type=event_type,
                payload=payload,
            )
        )

    @staticmethod
    def _to_view(row: Interview) -> InterviewView:
        return InterviewView(
            id=row.id,
            application_id=row.application_id,
            status=row.status.value if hasattr(row.status, "value") else str(row.status),
            title=row.title,
            scheduled_at=row.scheduled_at,
            notes=row.notes,
            round=row.round,
            format=row.format,
            interviewer=row.interviewer,
        )


class OfferService:
    def __init__(
        self,
        session: Session,
        user_id: uuid.UUID,
        *,
        events: UserEventPublisher | None = None,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._events = events

    def list_offers(self, *, application_id: uuid.UUID | None = None) -> list[OfferView]:
        q = self._session.query(Offer).filter(Offer.user_id == self._user_id)
        if application_id is not None:
            q = q.filter(Offer.application_id == application_id)
        rows = q.order_by(Offer.created_at.desc()).all()
        return [self._to_view(r) for r in rows]

    def get(self, offer_id: uuid.UUID) -> OfferView:
        return self._to_view(self._get(offer_id))

    def create(self, payload: OfferCreate) -> OfferView:
        self._get_application(payload.application_id)
        details = {
            **(payload.details or {}),
            "compensation": payload.compensation,
            "equity": payload.equity,
            "location": payload.location,
        }
        row = Offer(
            id=uuid.uuid4(),
            user_id=self._user_id,
            application_id=payload.application_id,
            status=payload.status,
            offer_deadline=payload.deadline,
            details={k: v for k, v in details.items() if v is not None},
        )
        self._session.add(row)
        self._session.add(
            ApplicationEvent(
                id=uuid.uuid4(),
                user_id=self._user_id,
                application_id=payload.application_id,
                event_type="offer_received",
                payload={"offer_id": str(row.id), "status": payload.status.value},
            )
        )
        self._session.commit()
        self._session.refresh(row)
        if self._events is not None:
            self._events.publish(
                self._user_id,
                UserEventType.offer_updated,
                {"offer_id": str(row.id), "application_id": str(payload.application_id)},
            )
        return self._to_view(row)

    def update(self, offer_id: uuid.UUID, payload: OfferUpdate) -> OfferView:
        row = self._get(offer_id)
        data = payload.model_dump(exclude_unset=True)
        if "deadline" in data:
            row.offer_deadline = data.pop("deadline")
        if "status" in data:
            row.status = data.pop("status")
        details = dict(row.details or {})
        for key in ("compensation", "equity", "location"):
            if key in data:
                details[key] = data.pop(key)
        if "details" in data and data["details"] is not None:
            details.update(data.pop("details"))
        row.details = details
        self._session.add(
            ApplicationEvent(
                id=uuid.uuid4(),
                user_id=self._user_id,
                application_id=row.application_id,
                event_type="offer_updated",
                payload={"offer_id": str(row.id)},
            )
        )
        self._session.commit()
        self._session.refresh(row)
        if self._events is not None:
            self._events.publish(
                self._user_id,
                UserEventType.offer_updated,
                {"offer_id": str(row.id)},
            )
        return self._to_view(row)

    def _get(self, offer_id: uuid.UUID) -> Offer:
        row = (
            self._session.query(Offer)
            .filter(Offer.id == offer_id, Offer.user_id == self._user_id)
            .one_or_none()
        )
        if row is None:
            raise NotFoundError("Offer not found")
        return row

    def _get_application(self, application_id: uuid.UUID) -> Application:
        row = (
            self._session.query(Application)
            .filter(Application.id == application_id, Application.user_id == self._user_id)
            .one_or_none()
        )
        if row is None:
            raise NotFoundError("Application not found")
        return row

    @staticmethod
    def _to_view(row: Offer) -> OfferView:
        details = row.details if isinstance(row.details, dict) else {}
        return OfferView(
            id=row.id,
            application_id=row.application_id,
            status=row.status.value if hasattr(row.status, "value") else str(row.status),
            offer_deadline=row.offer_deadline,
            compensation=details.get("compensation"),
            equity=details.get("equity"),
            location=details.get("location"),
            details=details,
        )
