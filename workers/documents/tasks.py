"""Document generation worker stubs."""

from __future__ import annotations

import logging
import uuid

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="generate_documents", max_retries=2)
def generate_documents(self, user_id: str, job_id: str, resume_version_id: str | None = None) -> dict:
    """Stub: resume customization / PDF generation runs via domain services in-process for now."""
    logger.info(
        "generate_documents stub task=%s user=%s job=%s resume=%s",
        self.request.id,
        user_id,
        job_id,
        resume_version_id,
    )
    return {
        "status": "stub",
        "user_id": user_id,
        "job_id": job_id,
        "resume_version_id": resume_version_id,
        "note": "Wire ResumeCustomizationService / ResumePdfService here",
    }


# Ensure uuid imported for future expansion without unused-import lint noise in stubs.
_ = uuid
