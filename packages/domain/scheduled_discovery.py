"""Scheduled discovery fan-out for active users (Celery beat or QStash)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy.orm import Session

from database.models.enums import UserStatus
from database.models.schema import User, UserPreference
from packages.domain.jobs import DiscoveryTriggerService
from packages.domain.provider_usage import (
    ProviderQuotaLimits,
    ProviderUsageService,
    QuotaExceededError,
)

logger = logging.getLogger(__name__)


class DiscoveryTaskClient(Protocol):
    def enqueue_discover_jobs(
        self,
        *,
        user_id: uuid.UUID,
        workflow_run_id: uuid.UUID,
        max_results: int,
    ) -> str: ...


def run_scheduled_discover_for_active_users(
    session: Session,
    task_client: DiscoveryTaskClient,
    *,
    max_users: int = 50,
) -> dict:
    """Enqueue discovery for active users respecting preferences / quotas.

    Skips suspended users and those with discovery_schedule.enabled == false.
    """
    enqueued: list[str] = []
    skipped: list[dict] = []
    users = (
        session.query(User)
        .filter(User.status == UserStatus.active)
        .order_by(User.created_at.asc())
        .limit(max_users)
        .all()
    )
    usage = ProviderUsageService(session, limits=ProviderQuotaLimits())
    for user in users:
        prefs_row = (
            session.query(UserPreference)
            .filter(UserPreference.user_id == user.id)
            .one_or_none()
        )
        payload = (
            prefs_row.settings if prefs_row and isinstance(prefs_row.settings, dict) else {}
        )
        schedule = payload.get("discovery_schedule") or {}
        if schedule.get("enabled") is False:
            skipped.append({"user_id": str(user.id), "reason": "disabled"})
            continue
        try:
            usage.check_quota(user.id, "search", units=1.0)
        except QuotaExceededError as exc:
            skipped.append(
                {
                    "user_id": str(user.id),
                    "reason": "quota",
                    "action": exc.action,
                }
            )
            continue
        try:
            trigger = DiscoveryTriggerService(session, user.id)
            result = trigger.enqueue(max_results=20)
            task_id = task_client.enqueue_discover_jobs(
                user_id=user.id,
                workflow_run_id=result.workflow_run_id,
                max_results=20,
            )
            trigger.attach_task_id(result.workflow_run_id, task_id)
            enqueued.append(str(result.workflow_run_id))
        except Exception as exc:
            logger.warning("scheduled_discovery_skip user=%s err=%s", user.id, exc)
            skipped.append({"user_id": str(user.id), "reason": str(exc)[:200]})
    return {
        "enqueued": enqueued,
        "skipped": skipped,
        "at": datetime.now(timezone.utc).isoformat(),
    }
