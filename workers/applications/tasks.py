"""Application workflow worker tasks."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from packages.domain.career_workflow import CareerWorkflowService, CareerWorkflowStart
from packages.providers.notification import MockNotificationProvider
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _session() -> Session:
    from app.database import get_session_factory, init_db

    init_db()
    return get_session_factory()()


def _run_career_workflow(
    user_id: uuid.UUID,
    job_match_id: uuid.UUID,
    *,
    permit_submit: bool,
    force: bool,
) -> dict:
    session = _session()
    try:
        service = CareerWorkflowService(
            session,
            user_id,
            notifications=MockNotificationProvider(),
        )
        result = service.start_or_resume(
            CareerWorkflowStart(
                job_match_id=job_match_id,
                permit_submit=permit_submit,
                force=force,
            )
        )
        return result.model_dump(mode="json")
    finally:
        session.close()


@celery_app.task(
    bind=True,
    name="run_career_workflow",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
)
def run_career_workflow(
    self,
    user_id: str,
    job_match_id: str,
    permit_submit: bool = False,
    force: bool = False,
) -> dict:
    logger.info(
        "run_career_workflow task=%s user=%s match=%s",
        self.request.id,
        user_id,
        job_match_id,
    )
    return _run_career_workflow(
        uuid.UUID(user_id),
        uuid.UUID(job_match_id),
        permit_submit=permit_submit,
        force=force,
    )
