"""Background embedding generation package."""

from workers.embeddings.tasks import (
    embed_company_research_task,
    embed_job_task,
    embed_profile_task,
    embed_resume_version_task,
)

__all__ = [
    "embed_company_research_task",
    "embed_job_task",
    "embed_profile_task",
    "embed_resume_version_task",
]
