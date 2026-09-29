"""Resend delivery webhooks — update Outreach tracking metadata."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from app.database import DbSessionDep
from database.models.schema import Outreach, OutreachEvent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/resend", tags=["webhooks"])


@router.post("")
async def resend_webhook(
    request: Request,
    session: DbSessionDep,
    svix_signature: str | None = Header(default=None, alias="svix-signature"),
) -> dict[str, str]:
    """Accept Resend webhook events (delivery, bounce, complaint)."""
    _ = svix_signature  # Verify when RESEND_WEBHOOK_SECRET is configured
    try:
        payload: dict[str, Any] = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc

    event_type = str(payload.get("type") or "")
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    message_id = data.get("email_id") or data.get("id")
    if not message_id:
        return {"status": "ignored"}

    event = (
        session.query(OutreachEvent)
        .filter(OutreachEvent.provider_event_id == str(message_id))
        .order_by(OutreachEvent.created_at.desc())
        .first()
    )
    if event is None:
        logger.info("resend_webhook_orphan message_id=%s type=%s", message_id, event_type)
        return {"status": "not_found"}

    outreach = session.query(Outreach).filter(Outreach.id == event.outreach_id).one_or_none()
    if outreach is None:
        return {"status": "not_found"}

    session.add(
        OutreachEvent(
            outreach_id=outreach.id,
            user_id=outreach.user_id,
            event_type=event_type or "resend_event",
            provider_event_id=str(message_id),
            payload=payload,
        )
    )
    session.commit()
    return {"status": "ok"}
