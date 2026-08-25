"""Contacts / people research worker tasks."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from packages.domain.people_research import PeopleResearchService
from packages.providers.factory import (
    ProviderSettings,
    create_email_finder_provider,
    create_email_verifier_provider,
    create_people_provider,
)
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _session() -> Session:
    from app.database import get_session_factory, init_db

    init_db()
    return get_session_factory()()


def _run_people_research(user_id: uuid.UUID, company_id: uuid.UUID) -> dict:
    settings = ProviderSettings.from_env()
    session = _session()
    try:
        service = PeopleResearchService(
            session,
            user_id,
            people=create_people_provider(settings),
            email_finder=create_email_finder_provider(settings),
            email_verifier=create_email_verifier_provider(settings),
        )
        result = service.research_company(company_id)
        return {
            "company_id": str(company_id),
            "people_count": len(result.people),
            "people": [p.model_dump(mode="json") for p in result.people[:20]],
        }
    finally:
        session.close()


@celery_app.task(
    bind=True,
    name="research_people_for_company",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def research_people_for_company(self, user_id: str, company_id: str) -> dict:
    logger.info(
        "research_people_for_company task=%s user=%s company=%s",
        self.request.id,
        user_id,
        company_id,
    )
    return _run_people_research(uuid.UUID(user_id), uuid.UUID(company_id))
