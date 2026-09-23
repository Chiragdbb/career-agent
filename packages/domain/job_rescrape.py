"""Force re-scrape a single job listing (bypasses freshness window)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from database.models.enums import WorkflowRunStatus
from database.models.schema import AuditLog, Company, Job, JobMatch, WorkflowRun
from packages.domain.discovery_logger import DiscoveryRunLogger
from packages.domain.exceptions import DomainError, NotFoundError
from packages.domain.job_discovery import job_fingerprint, normalize_job_url
from packages.domain.job_models import ExtractedJob
from packages.domain.llm_tasks import LLMTaskService
from packages.domain.notifications import NotificationService
from packages.domain.provider_usage import ProviderUsageContext, ProviderUsageService
from packages.domain.workflow_cancellation import WorkflowCancellation
from packages.domain.workflow_progress import WorkflowProgressService
from packages.providers.base import UsageInfo
from packages.providers.scraper import ScrapeRequest, ScraperProvider

if TYPE_CHECKING:
    from packages.domain.events import UserEventPublisher


class JobRescrapeService:
    def __init__(
        self,
        session: Session,
        user_id: uuid.UUID,
        *,
        scraper: ScraperProvider,
        llm_tasks: LLMTaskService,
        run_id: uuid.UUID | None = None,
        events: UserEventPublisher | None = None,
        cancellation: WorkflowCancellation | None = None,
        notifications: NotificationService | None = None,
        progress: WorkflowProgressService | None = None,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._scraper = scraper
        self._llm_tasks = llm_tasks
        self._run_id = run_id or uuid.uuid4()
        self._events = events
        self._cancellation = cancellation
        self._progress = progress or WorkflowProgressService(
            session,
            user_id,
            events=events,
            notifications=notifications,
        )

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

        run = self._load_run()
        if run is not None:
            run.status = WorkflowRunStatus.running
            meta = dict(run.metadata_json or {})
            meta["human_title"] = f"Updating {job.title or 'job listing'}"
            run.metadata_json = meta
            self._session.commit()
            self._progress.seed_eta(run, planned_units=1)

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
        self._checkpoint(run, "started", "Re-scrape started", phase="thinking", data={"url": url})
        self._raise_if_cancelled(run)

        status = "completed"
        try:
            self._checkpoint(
                run,
                "scrape",
                f"Scraping {url}",
                phase="working",
                data={"url": url, "provider": self._scraper.metadata.name},
            )
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
            self._checkpoint(
                run,
                "scrape",
                f"Scraped {len(markdown)} characters",
                phase="result",
                data={"url": url, "chars": len(markdown)},
            )
            self._raise_if_cancelled(run)

            self._checkpoint(
                run,
                "extract",
                "Extracting job details with LLM",
                phase="thinking",
                data={"url": url},
            )
            extracted = self._llm_tasks.extract_job(url=url, scraped_markdown=markdown)
            run_log.bump("extracts")
            self._checkpoint(
                run,
                "extract",
                f"Extracted “{extracted.title}”",
                phase="result",
                data={
                    "url": url,
                    "title": extracted.title,
                    "company": extracted.company_name,
                    "skills": extracted.skills[:12],
                },
            )
            self._raise_if_cancelled(run)
        except DomainError as exc:
            if "cancelled" in str(exc).lower():
                status = "cancelled"
                run_log.log("run_cancelled", error=str(exc))
                run_log.write_summary(status=status)
                raise
            status = "failed"
            run_log.errors.append(str(exc))
            run_log.log("run_failed", error=str(exc))
            run_log.write_summary(status=status)
            self._fail_run(run, str(exc))
            raise
        except Exception as exc:
            status = "failed"
            run_log.errors.append(str(exc))
            run_log.log("run_failed", error=str(exc))
            run_log.write_summary(status=status)
            self._fail_run(run, str(exc))
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
        self._complete_run(run, job)
        return job

    def _load_run(self) -> WorkflowRun | None:
        return (
            self._session.query(WorkflowRun)
            .filter(
                WorkflowRun.id == self._run_id,
                WorkflowRun.user_id == self._user_id,
            )
            .one_or_none()
        )

    def _raise_if_cancelled(self, run: WorkflowRun | None) -> None:
        if self._cancellation is None:
            return
        if self._cancellation.is_cancelled(self._run_id):
            if run is not None and run.status not in (
                WorkflowRunStatus.cancelled,
                WorkflowRunStatus.completed,
                WorkflowRunStatus.failed,
            ):
                run.status = WorkflowRunStatus.cancelled
                metadata = dict(run.metadata_json or {})
                metadata["current_step"] = "cancelled"
                metadata["status_message"] = "Re-scrape cancelled"
                run.metadata_json = metadata
                self._session.commit()
            raise DomainError("Re-scrape cancelled")

    def _checkpoint(
        self,
        run: WorkflowRun | None,
        step: str,
        message: str,
        *,
        phase: str,
        data: dict | None = None,
    ) -> None:
        display = None
        if data:
            display = {
                k: v
                for k, v in data.items()
                if k in {"company", "title", "count", "chars"}
            }
        if run is not None:
            self._progress.record_progress(
                run,
                step=step,
                message=message,
                phase=phase,
                display=display,
                completed_units=1 if phase == "result" and step in {"extract", "completed"} else None,
            )
            self._session.commit()
            return
        self._publish_progress(step=step, message=message, phase=phase, data=data)

    def _complete_run(self, run: WorkflowRun | None, job: Job) -> None:
        if run is None:
            self._publish(
                "workflow_completed",
                {
                    "workflow_run_id": str(self._run_id),
                    "workflow_type": "job_rescrape",
                    "status": "completed",
                    "job_id": str(job.id),
                    "title": job.title,
                },
            )
            return
        run.status = WorkflowRunStatus.completed
        metadata = dict(run.metadata_json or {})
        metadata["current_step"] = "completed"
        metadata["status_message"] = f"Updated “{job.title}”"
        metadata["title"] = job.title
        run.metadata_json = metadata
        run.error = None
        self._session.commit()
        self._progress.record_progress(
            run,
            step="completed",
            message=f"Updated “{job.title}”",
            phase="result",
            display={"title": job.title},
            completed_units=1,
            planned_units=1,
        )
        self._publish(
            "workflow_completed",
            {
                "workflow_run_id": str(self._run_id),
                "workflow_type": "job_rescrape",
                "status": "completed",
                "job_id": str(job.id),
                "title": job.title,
            },
        )
        self._progress.notify_terminal(
            run,
            status="completed",
            title="Job update finished",
            body=f"Updated “{job.title}”. Open Activity for details.",
        )

    def _fail_run(self, run: WorkflowRun | None, error: str) -> None:
        if run is not None:
            if run.status == WorkflowRunStatus.cancelled:
                return
            run.status = WorkflowRunStatus.failed
            run.error = error
            metadata = dict(run.metadata_json or {})
            metadata["current_step"] = "failed"
            metadata["status_message"] = f"Re-scrape failed: {error}"
            run.metadata_json = metadata
            self._session.commit()
            self._progress.record_progress(
                run,
                step="failed",
                message="Couldn’t update this job listing",
                phase="error",
            )
            self._progress.notify_terminal(
                run,
                status="failed",
                title="Job update failed",
                body="Something went wrong while refreshing the listing. Open Activity for details.",
            )
            return
        self._publish_progress(
            step="failed",
            message=f"Re-scrape failed: {error}",
            phase="error",
            data={"error": error},
        )
        self._publish(
            "workflow_failed",
            {
                "workflow_run_id": str(self._run_id),
                "workflow_type": "job_rescrape",
                "error": error,
            },
        )

    def _publish_progress(
        self,
        *,
        step: str,
        message: str,
        phase: str = "working",
        data: dict | None = None,
    ) -> None:
        payload_data = dict(data or {})
        payload_data.setdefault("phase", phase)
        self._publish(
            "workflow_progress",
            {
                "workflow_run_id": str(self._run_id),
                "workflow_type": "job_rescrape",
                "step": step,
                "phase": phase,
                "message": message,
                "data": payload_data,
            },
        )

    def _publish(self, event_type: str, payload: dict) -> None:
        if self._events is None:
            return
        from packages.domain.events import UserEventType

        self._events.publish(self._user_id, UserEventType(event_type), payload)

    def _apply_extraction(self, job: Job, extracted: ExtractedJob) -> None:
        now = datetime.now(timezone.utc)
        fingerprint = job_fingerprint(extracted)
        details = extracted.model_dump(mode="json")
        details["fingerprint"] = fingerprint
        job.title = extracted.title or job.title
        job.description = extracted.description or job.description
        job.details = details
        if extracted.seniority:
            job.seniority = extracted.seniority
        if extracted.employment_type:
            job.employment_type = extracted.employment_type
        if extracted.work_arrangement:
            job.remote_type = extracted.work_arrangement
        if extracted.salary_min is not None:
            job.salary_min = extracted.salary_min
        if extracted.salary_max is not None:
            job.salary_max = extracted.salary_max
        if extracted.currency:
            job.salary_currency = extracted.currency
        if extracted.skills:
            job.skills = extracted.skills
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
