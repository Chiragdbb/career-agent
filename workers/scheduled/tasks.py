"""Scheduled / periodic Celery tasks (discovery beat)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from database.models.enums import UserStatus
from database.models.schema import User, UserPreference
from packages.domain.jobs import DiscoveryTriggerService
from packages.domain.notifications import (
    NotificationCreate,
    NotificationService,
    NotificationType,
)
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _session() -> Session:
    from app.database import get_session_factory, init_db

    init_db()
    return get_session_factory()()


@celery_app.task(name="scheduled.discover_jobs_for_active_users")
def discover_jobs_for_active_users(max_users: int = 50) -> dict:
    """Enqueue discovery for active users respecting preferences / quotas.

    Driven by Celery beat. Skips suspended users and those with
    discovery_schedule.enabled == false.
    """
    from app.tasks import CeleryDiscoveryTaskClient
    from packages.domain.provider_usage import (
        ProviderQuotaLimits,
        ProviderUsageService,
        QuotaExceededError,
    )

    session = _session()
    enqueued: list[str] = []
    skipped: list[dict] = []
    try:
        users = (
            session.query(User)
            .filter(User.status == UserStatus.active)
            .order_by(User.created_at.asc())
            .limit(max_users)
            .all()
        )
        usage = ProviderUsageService(session, limits=ProviderQuotaLimits())
        client = CeleryDiscoveryTaskClient()
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
                task_id = client.enqueue_discover_jobs(
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
    finally:
        session.close()


@celery_app.task(name="scheduled.notify_high_fit_matches")
def notify_high_fit_matches(*, min_score: float = 0.75) -> dict:
    """Notify users about recent high-fit matches (best-effort)."""
    from database.models.schema import JobMatch
    from packages.providers.notification import MockNotificationProvider

    session = _session()
    notified = 0
    try:
        rows = (
            session.query(JobMatch)
            .filter(JobMatch.score.isnot(None), JobMatch.score >= min_score)
            .order_by(JobMatch.updated_at.desc())
            .limit(100)
            .all()
        )
        for match in rows:
            NotificationService(
                session, match.user_id, push_provider=MockNotificationProvider()
            ).create(
                NotificationCreate(
                    notification_type=NotificationType.high_priority_job,
                    title="High-fit opportunity",
                    body=f"Match score {match.score:.2f}",
                    data={"match_id": str(match.id)},
                    dedupe_key=f"high_fit:{match.id}",
                    send_email=False,
                )
            )
            notified += 1
        return {"notified": notified}
    finally:
        session.close()
