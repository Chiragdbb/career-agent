"""Job discovery worker tasks."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from packages.domain.job_discovery import JobDiscoveryService
from packages.domain.workflow_cancellation import WorkflowCancellation
from packages.providers.factory import (
    ProviderSettings,
    create_extraction_llm_provider,
    create_llm_provider,
    create_playwright_jobs_provider,
    create_scraper_provider,
    create_search_provider,
)
from packages.providers.exceptions import ProviderRateLimitDeferError
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _session() -> Session:
    from app.database import get_session_factory, init_db

    init_db()
    return get_session_factory()()


def _run_discovery(user_id: uuid.UUID, workflow_run_id: uuid.UUID, max_results: int) -> dict:
    from packages.shared.env import load_project_env

    load_project_env()
    settings = ProviderSettings.from_env()
    session = _session()
    try:
        events = _event_publisher()
        cancellation = _workflow_cancellation()
        discovery_lock = _discovery_lock()
        try:
            playwright_jobs = create_playwright_jobs_provider(settings)
        except Exception:
            logger.warning("playwright_jobs_create_failed", exc_info=True)
            playwright_jobs = None
        try:
            service = JobDiscoveryService(
                session,
                user_id,
                search=create_search_provider(settings),
                scraper=create_scraper_provider(settings),
                llm=create_llm_provider(settings),
                extraction_llm=create_extraction_llm_provider(settings),
                playwright_jobs=playwright_jobs,
                max_results=max_results,
                events=events,
                cancellation=cancellation,
                discovery_lock=discovery_lock,
                scrape_freshness_days=_scrape_freshness_days(),
            )
            result = service.run(workflow_run_id=workflow_run_id)
        except Exception as exc:
            _mark_run_failed(session, user_id, workflow_run_id, exc)
            if discovery_lock is not None:
                discovery_lock.release(user_id)
            raise
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


def _mark_run_failed(
    session: Session,
    user_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
    exc: Exception,
) -> None:
    try:
        from database.models.enums import WorkflowRunStatus
        from database.models.schema import WorkflowRun

        run = (
            session.query(WorkflowRun)
            .filter(WorkflowRun.id == workflow_run_id, WorkflowRun.user_id == user_id)
            .one_or_none()
        )
        if run is None:
            return
        if run.status in (
            WorkflowRunStatus.completed,
            WorkflowRunStatus.cancelled,
            WorkflowRunStatus.failed,
        ):
            return
        run.status = WorkflowRunStatus.failed
        run.error = str(exc)
        metadata = dict(run.metadata_json or {})
        metadata["current_step"] = "failed"
        metadata["status_message"] = f"Workflow failed: {exc}"
        run.metadata_json = metadata
        session.commit()
    except Exception:
        logger.warning("mark_run_failed_unsuccessful run=%s", workflow_run_id, exc_info=True)
        session.rollback()


def _event_publisher():
    try:
        from app.redis import get_redis
        from packages.domain.events import RedisEventBus, UserEventPublisher

        return UserEventPublisher(RedisEventBus(get_redis()))
    except Exception:
        logger.warning("event_publisher_unavailable", exc_info=True)
        return None


def _workflow_cancellation() -> WorkflowCancellation | None:
    try:
        from app.redis import get_redis
        from packages.domain.workflow_cancellation import WorkflowCancellation

        return WorkflowCancellation(get_redis())
    except Exception:
        logger.warning("workflow_cancellation_unavailable", exc_info=True)
        return None


def _discovery_lock():
    try:
        from app.redis import get_redis
        from packages.domain.discovery_lock import DiscoveryLock

        return DiscoveryLock(get_redis())
    except Exception:
        logger.warning("discovery_lock_unavailable", exc_info=True)
        return None


def _scrape_freshness_days() -> int:
    try:
        from app.config import get_settings

        return get_settings().job_scrape_freshness_days
    except Exception:
        return 14


@celery_app.task(
    bind=True,
    name="discover_jobs",
    autoretry_for=(ProviderRateLimitDeferError, Exception),
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


def _run_rescrape(
    user_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
    match_id: uuid.UUID,
) -> dict:
    from packages.domain.job_match import JobMatchService
    from packages.domain.job_rescrape import JobRescrapeService
    from packages.domain.jobs import load_resume_skills
    from packages.domain.llm_tasks import LLMTaskService
    from packages.shared.env import load_project_env

    load_project_env()
    settings = ProviderSettings.from_env()
    session = _session()
    try:
        events = _event_publisher()
        cancellation = _workflow_cancellation()
        service = JobRescrapeService(
            session,
            user_id,
            scraper=create_scraper_provider(settings),
            llm_tasks=LLMTaskService(
                create_llm_provider(settings),
                extraction_llm=create_extraction_llm_provider(settings),
            ),
            run_id=workflow_run_id,
            events=events,
            cancellation=cancellation,
        )
        job = service.rescrape(match_id)
        resume_skills = load_resume_skills(session, user_id)
        JobMatchService(session, user_id).upsert_match(job.id, resume_skills=resume_skills)
        return {
            "workflow_run_id": str(workflow_run_id),
            "match_id": str(match_id),
            "job_id": str(job.id),
            "title": job.title,
        }
    except Exception as exc:
        _mark_run_failed(session, user_id, workflow_run_id, exc)
        raise
    finally:
        session.close()


@celery_app.task(
    bind=True,
    name="rescrape_job",
    autoretry_for=(ProviderRateLimitDeferError,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=2,
)
def rescrape_job(
    self,
    user_id: str,
    workflow_run_id: str,
    match_id: str,
) -> dict:
    """Re-scrape a single job listing for a queued workflow run."""
    uid = uuid.UUID(user_id)
    run_id = uuid.UUID(workflow_run_id)
    mid = uuid.UUID(match_id)
    logger.info(
        "rescrape_job_start task=%s user=%s run=%s match=%s attempt=%s",
        self.request.id,
        uid,
        run_id,
        mid,
        self.request.retries + 1,
    )
    return _run_rescrape(uid, run_id, mid)
