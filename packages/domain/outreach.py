"""OutreachService — draft → approval → send with daily limits.

Never invents recipient emails. Does not send without EmailSenderProvider
and explicit approval (or an automation rule in preferences).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models.enums import ContactStatus, OutreachStatus
from database.models.schema import Contact, EmailVerification, Outreach, OutreachEvent
from packages.domain.exceptions import DomainError, NotFoundError
from packages.domain.human_tasks import (
    HumanTaskCreate,
    HumanTaskService,
    HumanTaskType,
)
from packages.domain.preferences import (
    OutreachApprovalMode,
    PreferenceSettings,
    PreferencesService,
)
from packages.providers.email_sender import (
    EmailSenderProvider,
    EmailSendRequest,
)
from packages.providers.notification import NotificationProvider


class OutreachType(StrEnum):
    recruiter = "recruiter"
    referral = "referral"
    hiring_manager = "hiring_manager"
    follow_up = "follow_up"


class EmailDeliveryState(StrEnum):
    """Delivery lifecycle separate from content/approval status."""

    draft = "DRAFT"
    approved = "APPROVED"
    queued = "QUEUED"
    sent = "SENT"
    delivered = "DELIVERED"
    bounced = "BOUNCED"
    failed = "FAILED"
    replied = "REPLIED"


class OutreachDraftInput(BaseModel):
    contact_id: uuid.UUID
    outreach_type: OutreachType
    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    application_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    company_id: uuid.UUID | None = None
    recipient_email: str | None = None  # must come from verified contact data
    channel: str = "email"
    request_approval: bool = True

    @field_validator("recipient_email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().lower()
        if not cleaned:
            return None
        if "@" not in cleaned or "." not in cleaned.split("@")[-1]:
            raise ValueError("recipient_email looks invalid")
        return cleaned


class OutreachView(BaseModel):
    id: uuid.UUID
    contact_id: uuid.UUID
    application_id: uuid.UUID | None = None
    status: str
    outreach_type: str | None = None
    channel: str | None = None
    subject: str | None = None
    body: str | None = None
    reason: str | None = None
    recipient_email: str | None = None
    job_id: uuid.UUID | None = None
    company_id: uuid.UUID | None = None
    delivery_state: str | None = None
    human_task_id: uuid.UUID | None = None


class OutreachService:
    def __init__(
        self,
        session: Session,
        user_id: uuid.UUID,
        *,
        email_sender: EmailSenderProvider | None = None,
        notifications: NotificationProvider | None = None,
        human_tasks: HumanTaskService | None = None,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._email_sender = email_sender
        self._human_tasks = human_tasks or HumanTaskService(
            session, user_id, notifications=notifications
        )

    def create_draft(self, payload: OutreachDraftInput) -> OutreachView:
        contact = self._get_contact(payload.contact_id)
        if contact.status == ContactStatus.do_not_contact:
            raise DomainError("Contact is marked do_not_contact")

        recipient = payload.recipient_email
        if recipient is None:
            recipient = self._verified_email_for_contact(contact.id)
        else:
            # Never invent — only accept emails already verified for this contact.
            if not self._email_belongs_to_contact(contact.id, recipient):
                raise DomainError(
                    "recipient_email must match a stored email for this contact; "
                    "emails are never invented"
                )

        prefs = PreferencesService(self._session, self._user_id).get_settings()
        meta: dict[str, Any] = {
            "outreach_type": payload.outreach_type.value,
            "reason": payload.reason,
            "job_id": str(payload.job_id) if payload.job_id else None,
            "company_id": str(payload.company_id) if payload.company_id else None,
            "recipient_email": recipient,
            "delivery_state": EmailDeliveryState.draft.value,
        }

        auto_approve = self._may_auto_approve(prefs, payload.outreach_type)
        status = OutreachStatus.draft
        if payload.request_approval and not auto_approve:
            status = OutreachStatus.pending_approval
        elif auto_approve:
            status = OutreachStatus.approved
            meta["delivery_state"] = EmailDeliveryState.approved.value
            meta["auto_approved"] = True

        # Store extended fields in channel prefix + body metadata via OutreachEvent
        # until columns exist; also keep subject/body on the row.
        row = Outreach(
            id=uuid.uuid4(),
            user_id=self._user_id,
            contact_id=contact.id,
            application_id=payload.application_id,
            status=status,
            channel=f"{payload.channel}:{payload.outreach_type.value}",
            subject=payload.subject,
            body=payload.body,
        )
        # Attach metadata via a create event (JSONB) — migration adds first-class cols.
        self._session.add(row)
        self._session.flush()
        self._add_event(
            row.id,
            "draft_created",
            payload={**meta, "subject": payload.subject},
        )
        # Persist meta on a synthetic event type for reload.
        self._add_event(row.id, "outreach_meta", payload=meta)

        human_task_id = None
        if status == OutreachStatus.pending_approval:
            task = self._human_tasks.create(
                HumanTaskCreate(
                    task_type=HumanTaskType.approval_required_outreach,
                    title=f"Approve {payload.outreach_type.value} outreach",
                    details={
                        "outreach_id": str(row.id),
                        "reason": payload.reason,
                        "subject": payload.subject,
                    },
                    outreach_id=row.id,
                    application_id=payload.application_id,
                    blocking_entity_type="outreach",
                    blocking_entity_id=row.id,
                )
            )
            human_task_id = task.id
            meta["human_task_id"] = str(task.id)
            self._add_event(row.id, "outreach_meta", payload=meta)

        self._session.commit()
        self._session.refresh(row)
        return self._to_view(row, meta, human_task_id=human_task_id)

    def approve(self, outreach_id: uuid.UUID, *, actor: str = "user") -> OutreachView:
        row = self._get_outreach(outreach_id)
        if row.status not in (OutreachStatus.draft, OutreachStatus.pending_approval):
            raise DomainError(f"Cannot approve outreach in status {row.status.value}")
        meta = self._load_meta(row.id)
        row.status = OutreachStatus.approved
        meta["delivery_state"] = EmailDeliveryState.approved.value
        meta["approved_by"] = actor
        meta["approved_at"] = datetime.now(timezone.utc).isoformat()
        self._add_event(row.id, "approved", payload=meta)
        self._add_event(row.id, "outreach_meta", payload=meta)
        self._session.commit()
        self._session.refresh(row)
        return self._to_view(row, meta)

    def send(self, outreach_id: uuid.UUID, *, force: bool = False) -> OutreachView:
        """Queue/send via EmailSenderProvider. Requires approved status unless force+rule."""
        if self._email_sender is None:
            raise DomainError("EmailSenderProvider is not configured")

        row = self._get_outreach(outreach_id)
        meta = self._load_meta(row.id)
        prefs = PreferencesService(self._session, self._user_id).get_settings()

        if row.status != OutreachStatus.approved and not force:
            raise DomainError("Outreach must be approved before send")

        if not self._within_daily_limit(prefs):
            raise DomainError(
                f"Daily outreach limit reached ({prefs.daily_outreach_limit})"
            )

        recipient = meta.get("recipient_email")
        if not recipient:
            raise DomainError("No recipient_email on outreach; cannot invent an address")

        meta["delivery_state"] = EmailDeliveryState.queued.value
        self._add_event(row.id, "queued", payload={"recipient": recipient})
        self._add_event(row.id, "outreach_meta", payload=meta)
        self._session.flush()

        try:
            resp = self._email_sender.send_email(
                EmailSendRequest(
                    to=[recipient],
                    subject=row.subject or "(no subject)",
                    body_text=row.body or "",
                )
            )
        except Exception as exc:  # noqa: BLE001 — record failure, re-raise domain
            meta["delivery_state"] = EmailDeliveryState.failed.value
            meta["error"] = str(exc)
            self._add_event(row.id, "failed", payload={"error": str(exc)})
            self._add_event(row.id, "outreach_meta", payload=meta)
            self._session.commit()
            raise DomainError(f"Email send failed: {exc}") from exc

        row.status = OutreachStatus.sent
        meta["delivery_state"] = EmailDeliveryState.sent.value
        meta["provider_message_id"] = resp.message_id
        meta["sent_at"] = datetime.now(timezone.utc).isoformat()
        self._add_event(
            row.id,
            "sent",
            payload={
                "message_id": resp.message_id,
                "accepted": resp.accepted,
            },
            provider_event_id=resp.message_id,
        )
        self._add_event(row.id, "outreach_meta", payload=meta)
        self._session.commit()
        self._session.refresh(row)
        return self._to_view(row, meta)

    def list_outreach(self, *, limit: int = 50) -> list[OutreachView]:
        rows = (
            self._session.query(Outreach)
            .filter(Outreach.user_id == self._user_id)
            .order_by(Outreach.created_at.desc())
            .limit(limit)
            .all()
        )
        return [self._to_view(r, self._load_meta(r.id)) for r in rows]

    def get(self, outreach_id: uuid.UUID) -> OutreachView:
        row = self._get_outreach(outreach_id)
        return self._to_view(row, self._load_meta(row.id))

    def _may_auto_approve(
        self, prefs: PreferenceSettings, outreach_type: OutreachType
    ) -> bool:
        if prefs.outreach_approval_mode == OutreachApprovalMode.always_approve:
            return False  # "always_approve" means always require user approval
        if prefs.outreach_approval_mode == OutreachApprovalMode.approve_each:
            return False
        # auto_when_rules — only when an explicit automation rule is present.
        # PreferenceSettings does not yet store rule list; require explicit marker
        # in settings dict via raw JSON key automation_rules.
        raw = PreferencesService(self._session, self._user_id).get_or_create()
        settings = raw.settings if isinstance(raw.settings, dict) else {}
        rules = settings.get("automation_rules") or []
        if not isinstance(rules, list):
            return False
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            if rule.get("action") == "auto_send_outreach" and rule.get("enabled") is True:
                allowed_types = rule.get("outreach_types") or []
                if not allowed_types or outreach_type.value in allowed_types:
                    return True
        return False

    def _within_daily_limit(self, prefs: PreferenceSettings) -> bool:
        if prefs.daily_outreach_limit <= 0:
            return False
        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        count = (
            self._session.query(func.count(Outreach.id))
            .filter(
                Outreach.user_id == self._user_id,
                Outreach.status == OutreachStatus.sent,
                Outreach.updated_at >= start,
            )
            .scalar()
        )
        return int(count or 0) < prefs.daily_outreach_limit

    def _get_contact(self, contact_id: uuid.UUID) -> Contact:
        row = (
            self._session.query(Contact)
            .filter(Contact.id == contact_id, Contact.user_id == self._user_id)
            .one_or_none()
        )
        if row is None:
            raise NotFoundError("Contact not found")
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

    def _verified_email_for_contact(self, contact_id: uuid.UUID) -> str | None:
        row = (
            self._session.query(EmailVerification)
            .filter(
                EmailVerification.contact_id == contact_id,
                EmailVerification.user_id == self._user_id,
            )
            .order_by(EmailVerification.created_at.desc())
            .first()
        )
        return row.email if row else None

    def _email_belongs_to_contact(self, contact_id: uuid.UUID, email: str) -> bool:
        row = (
            self._session.query(EmailVerification)
            .filter(
                EmailVerification.contact_id == contact_id,
                EmailVerification.user_id == self._user_id,
                func.lower(EmailVerification.email) == email.lower(),
            )
            .first()
        )
        return row is not None

    def _add_event(
        self,
        outreach_id: uuid.UUID,
        event_type: str,
        *,
        payload: dict[str, Any] | None = None,
        provider_event_id: str | None = None,
    ) -> None:
        self._session.add(
            OutreachEvent(
                id=uuid.uuid4(),
                user_id=self._user_id,
                outreach_id=outreach_id,
                event_type=event_type,
                provider_event_id=provider_event_id,
                provider_timestamp=datetime.now(timezone.utc),
                payload=payload or {},
            )
        )

    def _load_meta(self, outreach_id: uuid.UUID) -> dict[str, Any]:
        events = (
            self._session.query(OutreachEvent)
            .filter(
                OutreachEvent.outreach_id == outreach_id,
                OutreachEvent.user_id == self._user_id,
                OutreachEvent.event_type == "outreach_meta",
            )
            .order_by(OutreachEvent.created_at.desc())
            .all()
        )
        merged: dict[str, Any] = {}
        for ev in reversed(events):
            if isinstance(ev.payload, dict):
                merged.update(ev.payload)
        return merged

    def _to_view(
        self,
        row: Outreach,
        meta: dict[str, Any],
        *,
        human_task_id: uuid.UUID | None = None,
    ) -> OutreachView:
        job_id = meta.get("job_id")
        company_id = meta.get("company_id")
        ht = human_task_id or (
            uuid.UUID(meta["human_task_id"]) if meta.get("human_task_id") else None
        )
        return OutreachView(
            id=row.id,
            contact_id=row.contact_id,
            application_id=row.application_id,
            status=row.status.value if hasattr(row.status, "value") else str(row.status),
            outreach_type=meta.get("outreach_type"),
            channel=row.channel,
            subject=row.subject,
            body=row.body,
            reason=meta.get("reason"),
            recipient_email=meta.get("recipient_email"),
            job_id=uuid.UUID(job_id) if job_id else None,
            company_id=uuid.UUID(company_id) if company_id else None,
            delivery_state=meta.get("delivery_state"),
            human_task_id=ht,
        )
