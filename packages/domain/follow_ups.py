"""FollowUpService — schedule, cancel on reply, generate with approval gates."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models.enums import FollowUpStatus, OutreachStatus
from database.models.schema import Application, FollowUp, Outreach, OutreachEvent
from packages.domain.events import UserEventPublisher, UserEventType
from packages.domain.exceptions import DomainError, NotFoundError
from packages.domain.human_tasks import HumanTaskCreate, HumanTaskService, HumanTaskType
from packages.domain.notifications import NotificationCreate, NotificationService, NotificationType
from packages.domain.preferences import OutreachApprovalMode, PreferencesService
from packages.providers.notification import NotificationProvider


class FollowUpScheduleInput(BaseModel):
    outreach_id: uuid.UUID | None = None
    application_id: uuid.UUID | None = None
    days_after: int | None = Field(default=None, ge=1, le=90)
    subject: str | None = None
    body: str | None = None
    reason: str = "Scheduled follow-up after outreach"
    dedupe_key: str | None = None


class FollowUpView(BaseModel):
    id: uuid.UUID
    status: str
    next_action_at: datetime
    application_id: uuid.UUID | None = None
    outreach_id: uuid.UUID | None = None
    subject: str | None = None
    body: str | None = None
    reason: str | None = None
    cancelled_reason: str | None = None
    dedupe_key: str
    human_task_id: uuid.UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FollowUpService:
    """Manage follow-up cadence for applications and outreach sequences."""

    def __init__(
        self,
        session: Session,
        user_id: uuid.UUID,
        *,
        notifications: NotificationProvider | None = None,
        events: UserEventPublisher | None = None,
        notification_service: NotificationService | None = None,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._notifications = notifications
        self._events = events
        self._notification_service = notification_service

    def schedule(self, payload: FollowUpScheduleInput) -> FollowUpView:
        if payload.outreach_id is None and payload.application_id is None:
            raise DomainError("follow-up requires outreach_id or application_id")

        prefs = PreferencesService(self._session, self._user_id).get_settings()
        days = payload.days_after or prefs.follow_up_days_after_send
        next_at = datetime.now(timezone.utc) + timedelta(days=days)

        outreach = None
        application_id = payload.application_id
        if payload.outreach_id is not None:
            outreach = self._get_outreach(payload.outreach_id)
            if outreach.status == OutreachStatus.replied:
                raise DomainError("cannot schedule follow-up after a reply")
            if application_id is None:
                application_id = outreach.application_id

        if application_id is not None:
            self._get_application(application_id)

        dedupe = payload.dedupe_key or self._default_dedupe(
            outreach_id=payload.outreach_id,
            application_id=application_id,
        )
        existing = (
            self._session.query(FollowUp)
            .filter(FollowUp.user_id == self._user_id, FollowUp.dedupe_key == dedupe)
            .one_or_none()
        )
        if existing is not None:
            if existing.status in (
                FollowUpStatus.scheduled,
                FollowUpStatus.pending_approval,
            ):
                return self._to_view(existing)
            raise DomainError("follow-up already exists for this key")

        subject, body = self._generate_content(outreach, payload)
        row = FollowUp(
            id=uuid.uuid4(),
            user_id=self._user_id,
            application_id=application_id,
            outreach_id=payload.outreach_id,
            status=FollowUpStatus.scheduled,
            next_action_at=next_at,
            dedupe_key=dedupe,
            subject=subject,
            body=body,
            reason=payload.reason,
            metadata_json={"days_after": days},
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return self._to_view(row)

    def cancel_if_response(
        self,
        *,
        outreach_id: uuid.UUID | None = None,
        application_id: uuid.UUID | None = None,
        reason: str = "Response received",
    ) -> int:
        """Cancel open follow-ups when a reply/response exists."""
        q = self._session.query(FollowUp).filter(
            FollowUp.user_id == self._user_id,
            FollowUp.status.in_(
                [FollowUpStatus.scheduled, FollowUpStatus.pending_approval]
            ),
        )
        if outreach_id is not None:
            q = q.filter(FollowUp.outreach_id == outreach_id)
        elif application_id is not None:
            q = q.filter(FollowUp.application_id == application_id)
        else:
            raise DomainError("cancel_if_response requires outreach_id or application_id")

        if outreach_id is not None and not self._has_response(outreach_id):
            return 0

        cancelled = 0
        for row in q.all():
            row.status = FollowUpStatus.cancelled
            row.cancelled_reason = reason
            cancelled += 1
        if cancelled:
            self._session.commit()
        return cancelled

    def process_due(self, *, now: datetime | None = None, limit: int = 20) -> list[FollowUpView]:
        """Advance due follow-ups: notify + approval unless automation allows send."""
        now = now or datetime.now(timezone.utc)
        prefs = PreferencesService(self._session, self._user_id).get_settings()
        due = (
            self._session.query(FollowUp)
            .filter(
                FollowUp.user_id == self._user_id,
                FollowUp.status == FollowUpStatus.scheduled,
                FollowUp.next_action_at <= now,
            )
            .order_by(FollowUp.next_action_at.asc())
            .limit(limit)
            .all()
        )

        sent_today = self._followups_actioned_today(now)
        daily_limit = prefs.daily_outreach_limit
        results: list[FollowUpView] = []

        for row in due:
            if row.outreach_id and self._has_response(row.outreach_id):
                row.status = FollowUpStatus.cancelled
                row.cancelled_reason = "Response received"
                results.append(self._to_view(row))
                continue

            if sent_today >= daily_limit:
                break

            human_task_id = None
            auto = prefs.follow_up_auto_send and prefs.outreach_approval_mode in (
                OutreachApprovalMode.auto_when_rules,
                OutreachApprovalMode.always_approve,
            )
            if auto:
                row.status = FollowUpStatus.sent
                row.metadata_json = {
                    **(row.metadata_json or {}),
                    "auto_sent_at": now.isoformat(),
                }
            else:
                row.status = FollowUpStatus.pending_approval
                if self._notifications is not None:
                    task = HumanTaskService(
                        self._session, self._user_id, notifications=self._notifications
                    ).create(
                        HumanTaskCreate(
                            task_type=HumanTaskType.approval_required_outreach,
                            title=f"Approve follow-up: {row.subject or 'Follow-up'}",
                            details={
                                "follow_up_id": str(row.id),
                                "subject": row.subject,
                                "body": row.body,
                            },
                            outreach_id=row.outreach_id,
                            application_id=row.application_id,
                        )
                    )
                    human_task_id = task.id
                    row.metadata_json = {
                        **(row.metadata_json or {}),
                        "human_task_id": str(task.id),
                    }

            self._emit_due(row)
            sent_today += 1
            view = self._to_view(row)
            view.human_task_id = human_task_id
            results.append(view)

        self._session.commit()
        return results

    def list_follow_ups(
        self, *, status: FollowUpStatus | None = None
    ) -> list[FollowUpView]:
        q = self._session.query(FollowUp).filter(FollowUp.user_id == self._user_id)
        if status is not None:
            q = q.filter(FollowUp.status == status)
        rows = q.order_by(FollowUp.next_action_at.asc()).all()
        return [self._to_view(r) for r in rows]

    def get(self, follow_up_id: uuid.UUID) -> FollowUpView:
        return self._to_view(self._get(follow_up_id))

    def _emit_due(self, row: FollowUp) -> None:
        if self._notification_service is not None:
            self._notification_service.create(
                NotificationCreate(
                    notification_type=NotificationType.followup_due,
                    title="Follow-up due",
                    body=row.subject or "A follow-up action is due",
                    data={"follow_up_id": str(row.id)},
                    dedupe_key=f"followup-due:{row.id}",
                    send_email=True,
                )
            )
        if self._events is not None:
            self._events.publish(
                self._user_id,
                UserEventType.follow_up_due,
                {"follow_up_id": str(row.id)},
            )

    def _generate_content(
        self, outreach: Outreach | None, payload: FollowUpScheduleInput
    ) -> tuple[str, str]:
        if payload.subject and payload.body:
            return payload.subject, payload.body
        prior = (outreach.subject if outreach else None) or "our conversation"
        subject = payload.subject or f"Following up: {prior}"
        body = payload.body or (
            "Hi,\n\nI wanted to follow up on my previous note and remain "
            "available if helpful.\n\nThank you."
        )
        return subject, body

    def _has_response(self, outreach_id: uuid.UUID) -> bool:
        outreach = self._get_outreach(outreach_id)
        if outreach.status == OutreachStatus.replied:
            return True
        replied = (
            self._session.query(OutreachEvent)
            .filter(
                OutreachEvent.user_id == self._user_id,
                OutreachEvent.outreach_id == outreach_id,
                OutreachEvent.event_type.in_(["replied", "response_received"]),
            )
            .first()
        )
        return replied is not None

    def _followups_actioned_today(self, now: datetime) -> int:
        start = now.astimezone(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return (
            self._session.query(func.count(FollowUp.id))
            .filter(
                FollowUp.user_id == self._user_id,
                FollowUp.status.in_(
                    [FollowUpStatus.pending_approval, FollowUpStatus.sent]
                ),
                FollowUp.updated_at >= start,
            )
            .scalar()
            or 0
        )

    @staticmethod
    def _default_dedupe(
        *,
        outreach_id: uuid.UUID | None,
        application_id: uuid.UUID | None,
    ) -> str:
        if outreach_id is not None:
            return f"outreach:{outreach_id}:followup-1"
        return f"application:{application_id}:followup-1"

    def _get(self, follow_up_id: uuid.UUID) -> FollowUp:
        row = (
            self._session.query(FollowUp)
            .filter(FollowUp.id == follow_up_id, FollowUp.user_id == self._user_id)
            .one_or_none()
        )
        if row is None:
            raise NotFoundError("Follow-up not found")
        return row

    def _get_outreach(self, outreach_id: uuid.UUID) -> Outreach:
        row = (
            self._session.query(Outreach)
            .filter(Outreach.id == outreach_id, Outreach.user_id == self._user_id)
            .one_or_none()
        )
        if row is None:
            raise NotFoundError("Outreach not found")
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
    def _to_view(row: FollowUp) -> FollowUpView:
        meta = row.metadata_json if isinstance(row.metadata_json, dict) else {}
        human_task_id = None
        raw = meta.get("human_task_id")
        if raw:
            try:
                human_task_id = uuid.UUID(str(raw))
            except ValueError:
                human_task_id = None
        return FollowUpView(
            id=row.id,
            status=row.status.value if hasattr(row.status, "value") else str(row.status),
            next_action_at=row.next_action_at,
            application_id=row.application_id,
            outreach_id=row.outreach_id,
            subject=row.subject,
            body=row.body,
            reason=row.reason,
            cancelled_reason=row.cancelled_reason,
            dedupe_key=row.dedupe_key,
            human_task_id=human_task_id,
            metadata=meta,
        )
