"""Job discovery worker tasks."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from packages.domain.job_discovery import JobDiscoveryService
from packages.providers.factory import (
    ProviderSettings,
    create_llm_provider,
    create_scraper_provider,
    create_search_provider,
)
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _session() -> Session:
    from app.database import get_session_factory, init_db

    init_db()
    return get_session_factory()()


def _run_discovery(user_id: uuid.UUID, workflow_run_id: uuid.UUID, max_results: int) -> dict:
    settings = ProviderSettings.from_env()
    session = _session()
    try:
        service = JobDiscoveryService(
            session,
            user_id,
            search=create_search_provider(settings),
            scraper=create_scraper_provider(settings),
            llm=create_llm_provider(settings),
            max_results=max_results,
        )
        result = service.run(workflow_run_id=workflow_run_id)
        logger.info(
            "discovery_complete user=%s run=%s created=%d duplicates=%d skipped=%d",
            user_id,
            workflow_run_id,
            len(result.created_jobs),
            len(result.duplicate_jobs),
            result.skipped_invalid,
        )
        return {
            "workflow_run_id": str(result.workflow_run_id),
            "created_jobs": [str(job_id) for job_id in result.created_jobs],
            "duplicate_jobs": [str(job_id) for job_id in result.duplicate_jobs],
            "skipped_invalid": result.skipped_invalid,
            "errors": result.errors,
        }
    finally:
        session.close()


@celery_app.task(
    bind=True,
    name="discover_jobs",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=3,
)
def discover_jobs(
    self,
    user_id: str,
    workflow_run_id: str,
    max_results: int = 5,
) -> dict:
    """Run job discovery for a queued workflow run."""
    uid = uuid.UUID(user_id)
    run_id = uuid.UUID(workflow_run_id)
    logger.info(
        "discover_jobs_start task=%s user=%s run=%s attempt=%s",
        self.request.id,
        uid,
        run_id,
        self.request.retries + 1,
    )
    return _run_discovery(uid, run_id, max_results)
