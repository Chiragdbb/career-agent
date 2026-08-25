"""Outreach worker stubs."""

from __future__ import annotations

import logging

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="send_approved_outreach", max_retries=3)
def send_approved_outreach(self, user_id: str, outreach_id: str) -> dict:
    """Stub: actual send goes through OutreachService + EmailSenderProvider."""
    logger.info(
        "send_approved_outreach stub task=%s user=%s outreach=%s",
        self.request.id,
        user_id,
        outreach_id,
    )
    return {
        "status": "stub",
        "user_id": user_id,
        "outreach_id": outreach_id,
        "note": "Wire OutreachService.send with EmailSenderProvider in worker process",
    }
