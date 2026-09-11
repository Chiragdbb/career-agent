"""Background embedding generation tasks."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from packages.domain.embeddings import EmbeddingService
from packages.providers.factory import ProviderSettings, create_embedding_provider
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _session() -> Session:
    from app.database import get_session_factory, init_db

    init_db()
    return get_session_factory()()


def _service(session: Session) -> EmbeddingService:
    settings = ProviderSettings.from_env()
    return EmbeddingService(session, create_embedding_provider(settings))


@celery_app.task(name="embeddings.embed_job", bind=True, max_retries=3)
def embed_job_task(self, job_id: str) -> dict:
    session = _session()
    try:
        job = _service(session).embed_job(uuid.UUID(job_id))
        return {
            "job_id": str(job.id),
            "model": job.embedding_model,
            "version": job.embedding_version,
        }
    except Exception as exc:
        logger.exception("embed_job_failed job_id=%s", job_id)
        raise self.retry(exc=exc, countdown=30) from exc
    finally:
        session.close()


@celery_app.task(name="embeddings.embed_profile", bind=True, max_retries=3)
def embed_profile_task(self, user_id: str) -> dict:
    session = _session()
    try:
        profile = _service(session).embed_profile(uuid.UUID(user_id))
        return {
            "user_id": str(profile.user_id),
            "model": profile.embedding_model,
            "version": profile.embedding_version,
        }
    except Exception as exc:
        logger.exception("embed_profile_failed user_id=%s", user_id)
        raise self.retry(exc=exc, countdown=30) from exc
    finally:
        session.close()


@celery_app.task(name="embeddings.embed_company_research", bind=True, max_retries=3)
def embed_company_research_task(self, research_id: str) -> dict:
    session = _session()
    try:
        row = _service(session).embed_company_research(uuid.UUID(research_id))
        return {
            "research_id": str(row.id),
            "model": row.embedding_model,
            "version": row.embedding_version,
        }
    except Exception as exc:
        logger.exception("embed_company_research_failed id=%s", research_id)
        raise self.retry(exc=exc, countdown=30) from exc
    finally:
        session.close()


@celery_app.task(name="embeddings.embed_resume_version", bind=True, max_retries=3)
def embed_resume_version_task(self, version_id: str) -> dict:
    session = _session()
    try:
        row = _service(session).embed_resume_version(uuid.UUID(version_id))
        return {
            "version_id": str(row.id),
            "model": row.embedding_model,
            "version": row.embedding_version,
            "sections": list((row.section_embeddings or {}).keys()),
        }
    except Exception as exc:
        logger.exception("embed_resume_version_failed id=%s", version_id)
        raise self.retry(exc=exc, countdown=30) from exc
    finally:
        session.close()
