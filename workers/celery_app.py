"""Celery application for async workers."""

from __future__ import annotations

import os

from celery import Celery
from celery.signals import worker_process_init

from packages.shared.env import load_project_env
from packages.shared.logging import configure_logging

load_project_env()

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "career_agent",
    broker=redis_url,
    backend=redis_url,
    include=[
        "workers.discovery.tasks",
        "workers.research.tasks",
        "workers.contacts.tasks",
        "workers.documents.tasks",
        "workers.applications.tasks",
        "workers.outreach.tasks",
        "workers.notifications.tasks",
        "workers.embeddings.tasks",
        "workers.scheduled.tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_retry_delay=30,
    task_time_limit=900,
    task_soft_time_limit=840,
    beat_schedule={
        "discover-jobs-daily": {
            "task": "scheduled.discover_jobs_for_active_users",
            "schedule": 60 * 60 * 24,  # every 24h; override via CELERY_BEAT if needed
            "kwargs": {"max_users": 50},
        },
        "notify-high-fit-hourly": {
            "task": "scheduled.notify_high_fit_matches",
            "schedule": 60 * 60,
            "kwargs": {"min_score": 0.75},
        },
        "expire-package-artifacts-hourly": {
            "task": "scheduled.expire_package_artifacts",
            "schedule": 60 * 60,
            "kwargs": {"limit": 200},
        },
    },
)


@worker_process_init.connect
def _configure_worker_logging(**_kwargs: object) -> None:
    level = os.getenv("LOG_LEVEL", "INFO")
    configure_logging(level=level)
    from packages.shared.sentry import init_sentry

    init_sentry(service="celery")
