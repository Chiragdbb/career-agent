"""Celery application for async workers."""

from __future__ import annotations

import os

from celery import Celery

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "career_agent",
    broker=redis_url,
    backend=redis_url,
    include=["workers.discovery.tasks"],
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
)
