"""Notification worker stubs."""

from __future__ import annotations

import logging

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="deliver_notification", max_retries=3)
def deliver_notification(
    self,
    user_id: str,
    title: str,
    body: str = "",
    payload: dict | None = None,
) -> dict:
    """Stub: deliver via NotificationProvider (mock in CI)."""
    logger.info(
        "deliver_notification stub task=%s user=%s title=%s",
        self.request.id,
        user_id,
        title,
    )
    return {
        "status": "stub",
        "user_id": user_id,
        "title": title,
        "body": body,
        "payload": payload or {},
        "note": "Wire NotificationProvider.send here",
    }
