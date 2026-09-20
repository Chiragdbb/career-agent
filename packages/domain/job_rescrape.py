"""Force re-scrape a single job listing (bypasses freshness window)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from database.models.schema import AuditLog, Company, Job, JobMatch
from packages.domain.discovery_logger import DiscoveryRunLogger
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
        run_id: uuid.UUID | None = None,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._scraper = scraper
        self._llm_tasks = llm_tasks
        self._run_id = run_id or uuid.uuid4()

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

        run_log = DiscoveryRunLogger(self._run_id, workflow_type="job_rescrape")
        run_log.config = {
            "scraper_provider": self._scraper.metadata.name,
            "prompt_version": self._llm_tasks.prompt_version,
            "bodies_enabled": run_log.bodies_enabled,
            "snippet_chars": run_log.snippet_chars,
            "match_id": str(match_id),
            "job_id": str(job.id),
        }
        run_log.knobs_touched = [
            "FIRECRAWL_BASE_URL",
            "FIRECRAWL_API_KEY",
            "EXTRACTION_LLM_PROVIDER",
        ]
        self._llm_tasks._discovery_log = run_log
        run_log.log("run_started", url=url, config=run_log.config)
        status = "completed"
        try:
            run_log.log("scrape_request", url=url, provider=self._scraper.metadata.name)
            scraped = self._scraper.scrape_url(ScrapeRequest(url=url))
            markdown = scraped.markdown or scraped.title or ""
            if not markdown.strip():
                raise DomainError("Scraper returned empty content")
            run_log.bump("scrapes")
            scrape_fields = {
                "url": url,
                "chars": len(markdown),
                "content_source": "scrape",
            }
            scrape_fields.update(
                run_log.payload_fields(
                    text=markdown,
                    snippet_key="scraped_snippet",
                    body_key="scraped_markdown",
                )
            )
            run_log.log("scrape_result", **scrape_fields)
            extracted = self._llm_tasks.extract_job(url=url, scraped_markdown=markdown)
            run_log.bump("extracts")
        except DomainError as exc:
            status = "failed"
            run_log.errors.append(str(exc))
            run_log.log("run_failed", error=str(exc))
            run_log.write_summary(status=status)
            raise
        except Exception as exc:
            status = "failed"
            run_log.errors.append(str(exc))
            run_log.log("run_failed", error=str(exc))
            run_log.write_summary(status=status)
            raise DomainError(f"Re-scrape failed: {exc}") from exc

        self._apply_extraction(job, extracted)
        self._record_usage()
        self._audit(
            match_id,
            before=before,
            after={
                "title": job.title,
                "description": job.description,
                "details": job.details,
            },
        )
        self._session.commit()
        self._session.refresh(job)
        run_log.log("job_updated", job_id=str(job.id), title=job.title, url=url)
        run_log.log("run_completed", job_id=str(job.id))
        run_log.write_summary(
            status=status,
            usage=ProviderUsageService(self._session).summarize_workflow_run(
                workflow_run_id=self._run_id,
                user_id=self._user_id,
            ),
        )
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
            context=ProviderUsageContext(
                user_id=self._user_id,
                workflow_run_id=self._run_id,
            ),
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
