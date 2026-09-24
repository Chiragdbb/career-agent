"""Scheduled / periodic Celery tasks (discovery beat)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from packages.domain.notifications import (
    NotificationCreate,
    NotificationService,
    NotificationType,
)
from workers.celery_app import celery_app


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
    from packages.domain.scheduled_discovery import run_scheduled_discover_for_active_users

    session = _session()
    try:
        return run_scheduled_discover_for_active_users(
            session, CeleryDiscoveryTaskClient(), max_users=max_users
        )
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
