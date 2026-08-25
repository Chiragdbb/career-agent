"""Research worker tasks."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from packages.domain.company_research import CompanyResearchService
from packages.domain.llm_tasks import LLMTaskService
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


def _run_company_research(user_id: uuid.UUID, job_id: uuid.UUID, force_refresh: bool) -> dict:
    settings = ProviderSettings.from_env()
    session = _session()
    try:
        llm = create_llm_provider(settings)
        service = CompanyResearchService(
            session,
            user_id,
            search=create_search_provider(settings),
            scraper=create_scraper_provider(settings),
            llm_tasks=LLMTaskService(llm),
        )
        row = service.research_for_job(job_id, force_refresh=force_refresh)
        return {
            "company_research_id": str(row.id),
            "company_id": str(row.company_id),
            "status": row.status.value if hasattr(row.status, "value") else str(row.status),
        }
    finally:
        session.close()


@celery_app.task(
    bind=True,
    name="research_company_for_job",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def research_company_for_job(
    self,
    user_id: str,
    job_id: str,
    force_refresh: bool = False,
) -> dict:
    logger.info("research_company_for_job task=%s user=%s job=%s", self.request.id, user_id, job_id)
    return _run_company_research(uuid.UUID(user_id), uuid.UUID(job_id), force_refresh)
