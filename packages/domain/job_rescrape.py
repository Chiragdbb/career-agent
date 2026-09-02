"""Force re-scrape a single job listing (bypasses freshness window)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from database.models.schema import AuditLog, Company, Job, JobMatch
from packages.domain.exceptions import DomainError, NotFoundError
from packages.domain.job_discovery import job_fingerprint, normalize_job_url
from packages.domain.job_models import ExtractedJob
from packages.domain.llm_tasks import LLMTaskService
from packages.domain.provider_usage import ProviderUsageContext, ProviderUsageService
from packages.providers.base import UsageInfo
from packages.providers.scraper import ScrapeRequest, ScraperProvider


class JobRescrapeService:
    def __init__(
        self,
        session: Session,
        user_id: uuid.UUID,
        *,
        scraper: ScraperProvider,
        llm_tasks: LLMTaskService,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._scraper = scraper
        self._llm_tasks = llm_tasks

    def rescrape(self, match_id: uuid.UUID) -> Job:
        row = (
            self._session.query(JobMatch, Job, Company)
            .join(Job, Job.id == JobMatch.job_id)
            .join(Company, Company.id == Job.company_id)
            .filter(JobMatch.id == match_id, JobMatch.user_id == self._user_id)
            .one_or_none()
        )
        if row is None:
            raise NotFoundError("Job not found")
        _match, job, _company = row
        if not job.url:
            raise DomainError("Job has no source URL to re-scrape")

        url = normalize_job_url(job.url)
        before = {
            "title": job.title,
            "description": job.description,
            "details": job.details,
        }

        try:
            scraped = self._scraper.scrape_url(ScrapeRequest(url=url))
            markdown = scraped.markdown or scraped.title or ""
            if not markdown.strip():
                raise DomainError("Scraper returned empty content")
            extracted = self._llm_tasks.extract_job(url=url, scraped_markdown=markdown)
        except DomainError:
            raise
        except Exception as exc:
            raise DomainError(f"Re-scrape failed: {exc}") from exc

        self._apply_extraction(job, extracted)
        self._record_usage()
        self._audit(match_id, before=before, after={
            "title": job.title,
            "description": job.description,
            "details": job.details,
        })
        self._session.commit()
        self._session.refresh(job)
        return job

    def _apply_extraction(self, job: Job, extracted: ExtractedJob) -> None:
        now = datetime.now(timezone.utc)
        fingerprint = job_fingerprint(extracted)
        details = extracted.model_dump(mode="json")
        details["fingerprint"] = fingerprint
        job.title = extracted.title or job.title
        job.description = extracted.description or job.description
        job.details = details
        job.last_scraped_at = now

    def _record_usage(self) -> None:
        ProviderUsageService(self._session).record(
            context=ProviderUsageContext(user_id=self._user_id),
            provider_name=self._scraper.metadata.name,
            operation="manual_rescrape",
            usage=UsageInfo(operation="manual_rescrape", unit_type="requests", units=1.0),
            success=True,
        )

    def _audit(self, match_id: uuid.UUID, *, before: dict, after: dict) -> None:
        self._session.add(
            AuditLog(
                user_id=self._user_id,
                actor_type="user",
                action="manual_rescrape",
                entity_type="job_match",
                entity_id=match_id,
                before=before,
                after=after,
                metadata_json={"source": "job_rescrape"},
            )
        )
