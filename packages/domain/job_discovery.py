"""Job discovery: preferences → search → scrape → extract → normalize → persist.

Uses provider interfaces only. Idempotent on job URL / external_id.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from urllib.parse import urlparse, urlunparse

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models.enums import (
    CompanyStatus,
    JobMatchStatus,
    JobStatus,
    WorkflowRunStatus,
    WorkflowTaskStatus,
)
from database.models.schema import Company, Job, JobMatch, WorkflowRun, WorkflowTask
from packages.domain.discovery_logger import DiscoveryFileLogger
from packages.domain.exceptions import DiscoveryCancelledError, DomainError, NotFoundError
from packages.domain.extraction_constants import EXTRACTION_CONTENT_PREFILTER_MAX_CHARS
from packages.domain.events import UserEventPublisher, UserEventType
from packages.domain.job_match import JobMatchService
from packages.domain.job_urls import is_likely_listing_page
from packages.domain.workflow_cancellation import WorkflowCancellation
from packages.providers.exceptions import ProviderError
from packages.domain.job_models import ExtractedJob
from packages.domain.jobs import load_resume_skills
from packages.domain.llm_tasks import LLMTaskService
from packages.domain.preferences import PreferenceSettings, PreferencesService
from packages.providers.llm import LLMProvider
from packages.providers.scraper import ScrapeRequest, ScraperProvider
from packages.providers.search import SearchProvider, SearchRequest

logger = logging.getLogger("career.fetch")


@dataclass
class DiscoveryResult:
    workflow_run_id: uuid.UUID
    created_jobs: list[uuid.UUID] = field(default_factory=list)
    duplicate_jobs: list[uuid.UUID] = field(default_factory=list)
    skipped_invalid: int = 0
    errors: list[str] = field(default_factory=list)


class JobDiscoveryService:
    """Discover and ingest jobs for one tenant using mocked or real providers."""

    def __init__(
        self,
        session: Session,
        user_id: uuid.UUID,
        *,
        search: SearchProvider,
        scraper: ScraperProvider,
        llm: LLMProvider,
        extraction_llm: LLMProvider | None = None,
        max_results: int = 5,
        events: UserEventPublisher | None = None,
        cancellation: WorkflowCancellation | None = None,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._search = search
        self._scraper = scraper
        self._llm = llm
        self._extraction_llm = extraction_llm or llm
        self._llm_tasks = LLMTaskService(llm, extraction_llm=self._extraction_llm)
        self._max_results = max_results
        self._events = events
        self._cancellation = cancellation
        self._url_context: dict[str, dict[str, str]] = {}
        self._file_log: DiscoveryFileLogger | None = None

    def run(
        self,
        *,
        preferences: PreferenceSettings | None = None,
        workflow_run_id: uuid.UUID | None = None,
    ) -> DiscoveryResult:
        prefs = preferences or PreferencesService(self._session, self._user_id).get_settings()
        if workflow_run_id is not None:
            run = (
                self._session.query(WorkflowRun)
                .filter(
                    WorkflowRun.id == workflow_run_id,
                    WorkflowRun.user_id == self._user_id,
                )
                .one_or_none()
            )
            if run is None:
                raise NotFoundError("Workflow run not found")
            run.status = WorkflowRunStatus.running
            metadata = dict(run.metadata_json or {})
            metadata.setdefault("prompt_version", self._llm_tasks.prompt_version)
            metadata["max_results"] = self._max_results
            metadata["current_step"] = "starting"
            run.metadata_json = metadata
            self._session.flush()
            self._publish_progress(
                run_id=run.id,
                step="starting",
                message="Job discovery started",
                data={"status": "running"},
            )
        else:
            run = WorkflowRun(
                id=uuid.uuid4(),
                user_id=self._user_id,
                status=WorkflowRunStatus.running,
                workflow_type="job_discovery",
                metadata_json={
                    "prompt_version": self._llm_tasks.prompt_version,
                    "max_results": self._max_results,
                },
            )
            self._session.add(run)
            self._session.flush()

        result = DiscoveryResult(workflow_run_id=run.id)
        self._file_log = DiscoveryFileLogger(run.id)
        self._llm_tasks = LLMTaskService(
            self._llm,
            extraction_llm=self._extraction_llm,
            discovery_log=self._file_log,
        )
        self._file_log.log(
            "discovery_started",
            user_id=str(self._user_id),
            max_results=self._max_results,
        )
        try:
            queries = _build_queries(prefs)
            self._update_run_metadata(
                run,
                current_step="search",
                message="Planning search queries from your preferences…",
            )
            urls = self._search_urls(queries, run.id, result)
            self._ensure_not_cancelled(run)
            self._update_run_metadata(
                run,
                current_step="ingest",
                message=f"Found {len(urls)} listings — reading and extracting job details…",
                urls_found=len(urls),
            )
            for url in urls:
                self._ensure_not_cancelled(run)
                self._ingest_url(url, run.id, result)
            self._ensure_not_cancelled(run)
            self._update_run_metadata(run, current_step="scoring", message="Scoring matches against your profile…")
            self._score_discovered_jobs(result, prefs)
            run.status = WorkflowRunStatus.completed
            metadata = dict(run.metadata_json or {})
            metadata["current_step"] = "completed"
            metadata["created_jobs"] = len(result.created_jobs)
            metadata["duplicate_jobs"] = len(result.duplicate_jobs)
            metadata["skipped_invalid"] = result.skipped_invalid
            metadata["errors"] = result.errors
            run.metadata_json = metadata
            self._session.commit()
            self._publish(
                UserEventType.jobs_discovered,
                {
                    "workflow_run_id": str(run.id),
                    "workflow_type": "job_discovery",
                    "created_count": len(result.created_jobs),
                    "duplicate_count": len(result.duplicate_jobs),
                    "skipped_invalid": result.skipped_invalid,
                    "errors": result.errors,
                },
            )
            self._publish(
                UserEventType.workflow_completed,
                {
                    "workflow_run_id": str(run.id),
                    "workflow_type": "job_discovery",
                    "status": "completed",
                    "created_count": len(result.created_jobs),
                    "duplicate_count": len(result.duplicate_jobs),
                },
            )
            self._file_log.log(
                "discovery_completed",
                created=len(result.created_jobs),
                duplicates=len(result.duplicate_jobs),
                skipped=result.skipped_invalid,
                errors=result.errors,
            )
        except DiscoveryCancelledError:
            run.status = WorkflowRunStatus.cancelled
            metadata = dict(run.metadata_json or {})
            metadata["current_step"] = "cancelled"
            metadata["status_message"] = "Discovery cancelled"
            metadata["created_jobs"] = len(result.created_jobs)
            metadata["duplicate_jobs"] = len(result.duplicate_jobs)
            metadata["skipped_invalid"] = result.skipped_invalid
            metadata["errors"] = result.errors
            run.metadata_json = metadata
            run.error = None
            self._session.commit()
            self._publish(
                UserEventType.workflow_cancelled,
                {
                    "workflow_run_id": str(run.id),
                    "workflow_type": "job_discovery",
                    "created_count": len(result.created_jobs),
                    "duplicate_count": len(result.duplicate_jobs),
                },
            )
            logger.info("discovery_cancelled run_id=%s", run.id)
            self._file_log.log("discovery_cancelled", errors=result.errors)
            return result
        except Exception as exc:
            run.status = WorkflowRunStatus.failed
            run.error = str(exc)
            metadata = dict(run.metadata_json or {})
            metadata["current_step"] = "failed"
            metadata["errors"] = result.errors + [str(exc)]
            run.metadata_json = metadata
            self._session.commit()
            self._publish(
                UserEventType.workflow_failed,
                {
                    "workflow_run_id": str(run.id),
                    "workflow_type": "job_discovery",
                    "error": str(exc),
                },
            )
            logger.error("ERROR discovery run_id=%s error=%s", run.id, exc, exc_info=True)
            self._file_log.log("discovery_failed", error=str(exc), errors=result.errors)
            raise
        return result

    def _ensure_not_cancelled(self, run: WorkflowRun) -> None:
        self._session.refresh(run)
        if run.status == WorkflowRunStatus.cancelled:
            raise DiscoveryCancelledError("Discovery cancelled by user")
        if self._cancellation is not None and self._cancellation.is_cancelled(run.id):
            run.status = WorkflowRunStatus.cancelled
            self._session.flush()
            raise DiscoveryCancelledError("Discovery cancelled by user")

    def _score_discovered_jobs(
        self, result: DiscoveryResult, prefs: PreferenceSettings
    ) -> None:
        job_ids = list(dict.fromkeys(result.created_jobs + result.duplicate_jobs))
        if not job_ids:
            return
        resume_skills = load_resume_skills(self._session, self._user_id)
        matcher = JobMatchService(self._session, self._user_id)
        for job_id in job_ids:
            matcher.upsert_match(job_id, preferences=prefs, resume_skills=resume_skills)

    def _search_urls(
        self, queries: list[str], run_id: uuid.UUID, result: DiscoveryResult
    ) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for query in queries:
            run = (
                self._session.query(WorkflowRun)
                .filter(WorkflowRun.id == run_id)
                .one()
            )
            self._ensure_not_cancelled(run)
            task = self._start_task(run_id, "search", {"query": query})
            provider = self._search.metadata.name
            self._publish_progress(
                run_id=run_id,
                step="search",
                phase="thinking",
                message=f"Searching the web for “{query}”…",
                data={"provider": provider, "query": query, "status": "running"},
            )
            logger.info("FETCH search provider=%s query=%r", provider, query)
            try:
                response = self._search.search(
                    SearchRequest(query=query, max_results=self._max_results)
                )
                found = []
                for hit in response.results:
                    normalized = normalize_job_url(str(hit.url))
                    if normalized and normalized not in seen:
                        if is_likely_listing_page(normalized):
                            logger.info("SKIP listing page url=%s", normalized)
                            self._file_log.log(
                                "url_skipped",
                                url=normalized,
                                reason="listing_page",
                                query=query,
                            )
                            continue
                        seen.add(normalized)
                        ordered.append(normalized)
                        found.append(normalized)
                        self._url_context[normalized] = {
                            "title": str(hit.title or ""),
                            "snippet": str(hit.snippet or ""),
                            "query": query,
                        }
                self._complete_task(task, {"urls": found})
                self._publish_progress(
                    run_id=run_id,
                    step="search",
                    phase="result",
                    message=f"Found {len(found)} listing{'s' if len(found) != 1 else ''} for “{query}”.",
                    data={
                        "provider": provider,
                        "query": query,
                        "urls": found,
                        "result_count": len(response.results),
                        "status": "completed",
                    },
                )
                logger.info(
                    "RECEIVED search provider=%s results=%d urls=%s",
                    provider,
                    len(response.results),
                    found,
                )
            except Exception as exc:
                self._fail_task(task, str(exc))
                result.errors.append(f"search:{query}:{exc}")
                self._publish_progress(
                    run_id=run_id,
                    step="search",
                    phase="error",
                    message=f"Search failed for “{query}”: {exc}",
                    data={"provider": provider, "query": query, "error": str(exc), "status": "failed"},
                )
                logger.error(
                    "ERROR search provider=%s query=%r error=%s",
                    provider,
                    query,
                    exc,
                )
        return ordered

    def _ingest_url(self, url: str, run_id: uuid.UUID, result: DiscoveryResult) -> None:
        if is_likely_listing_page(url):
            logger.info("SKIP listing page ingest url=%s", url)
            self._file_log.log("url_skipped", url=url, reason="listing_page")
            result.skipped_invalid += 1
            return

        existing = self._session.query(Job).filter(Job.url == url).one_or_none()
        if existing is not None:
            self._ensure_match(existing.id)
            result.duplicate_jobs.append(existing.id)
            return

        task = self._start_task(run_id, "ingest_url", {"url": url})
        scrape_provider = self._scraper.metadata.name
        ctx = self._url_context.get(url, {})
        try:
            self._publish_progress(
                run_id=run_id,
                step="ingest_url",
                phase="thinking",
                message=f"Reading job page at {self._short_url(url)}…",
                data={
                    "url": url,
                    "title": ctx.get("title"),
                    "provider": scrape_provider,
                    "status": "running",
                },
            )
            markdown, content_source = self._scrape_markdown(url)
            self._file_log.log(
                "scrape_result",
                url=url,
                content_source=content_source,
                chars=len(markdown),
            )
            if (
                content_source == "scrape"
                and len(markdown) > EXTRACTION_CONTENT_PREFILTER_MAX_CHARS
            ):
                raise DomainError(
                    f"Scraped content too large ({len(markdown)} chars) — "
                    "likely a listing page, not a single job posting"
                )
            if content_source == "search_snippet":
                self._publish_progress(
                    run_id=run_id,
                    step="ingest_url",
                    phase="thinking",
                    message=(
                        f"Scraper unavailable — using search preview for "
                        f"“{ctx.get('title') or self._short_url(url)}”."
                    ),
                    data={
                        "url": url,
                        "fallback": "search_snippet",
                        "provider": scrape_provider,
                        "status": "fallback",
                    },
                )
            self._publish_progress(
                run_id=run_id,
                step="extract_job",
                phase="thinking",
                message="Extracting role, skills, and requirements with AI…",
                data={"url": url, "content_source": content_source, "status": "running"},
            )
            extracted = self._llm_tasks.extract_job(url=url, scraped_markdown=markdown)
            self._file_log.log(
                "extract_success",
                url=url,
                title=extracted.title,
                company=extracted.company_name,
            )
            job = self._persist_extracted(extracted)
            result.created_jobs.append(job.id)
            self._complete_task(
                task,
                {
                    "job_id": str(job.id),
                    "title": job.title,
                    "company_id": str(job.company_id),
                    "content_source": content_source,
                },
            )
            self._publish_progress(
                run_id=run_id,
                step="ingest_url",
                phase="result",
                message=f"Added “{job.title}” at {extracted.company_name or 'unknown company'}.",
                data={
                    "url": url,
                    "job_id": str(job.id),
                    "title": job.title,
                    "company": extracted.company_name,
                    "content_source": content_source,
                    "status": "completed",
                },
            )
            logger.info(
                "RECEIVED job url=%s title=%r company=%r job_id=%s source=%s",
                url,
                job.title,
                extracted.company_name,
                job.id,
                content_source,
            )
        except DomainError as exc:
            result.skipped_invalid += 1
            self._fail_task(task, str(exc))
            result.errors.append(f"ingest:{url}:{exc}")
            self._publish_progress(
                run_id=run_id,
                step="ingest_url",
                phase="error",
                message=f"Could not extract job from {self._short_url(url)}: {exc}",
                data={"url": url, "error": str(exc), "status": "skipped"},
            )
            logger.error("ERROR ingest url=%s error=%s", url, exc)
            self._file_log.log("extract_skipped", url=url, error=str(exc))
        except Exception as exc:
            self._fail_task(task, str(exc))
            result.errors.append(f"ingest:{url}:{exc}")
            self._publish_progress(
                run_id=run_id,
                step="ingest_url",
                phase="error",
                message=f"Failed to process {self._short_url(url)}: {exc}",
                data={"url": url, "error": str(exc), "status": "failed"},
            )
            logger.error("ERROR ingest url=%s error=%s", url, exc, exc_info=True)
            self._file_log.log("ingest_failed", url=url, error=str(exc))

    def _scrape_markdown(self, url: str) -> tuple[str, str]:
        scrape_provider = self._scraper.metadata.name
        try:
            logger.info("FETCH scrape provider=%s url=%s", scrape_provider, url)
            scraped = self._scraper.scrape_url(ScrapeRequest(url=url))
            markdown = scraped.markdown or scraped.title or ""
            logger.info(
                "RECEIVED scrape provider=%s url=%s title=%r chars=%d",
                scrape_provider,
                url,
                scraped.title,
                len(markdown),
            )
            if markdown.strip():
                return markdown, "scrape"
        except (ProviderError, OSError, ConnectionError) as exc:
            logger.warning("SCRAPE_FALLBACK url=%s provider=%s error=%s", url, scrape_provider, exc)
            self._file_log.log(
                "scrape_failed",
                url=url,
                provider=scrape_provider,
                error=str(exc),
            )

        ctx = self._url_context.get(url, {})
        title = ctx.get("title") or "Job posting"
        snippet = ctx.get("snippet") or ""
        if not snippet.strip():
            raise DomainError(
                f"Could not read page and no search preview available for {url}"
            )
        markdown = f"# {title}\n\nSource: {url}\n\n{snippet}"
        return markdown, "search_snippet"

    @staticmethod
    def _short_url(url: str) -> str:
        try:
            parsed = urlparse(url)
            path = parsed.path.rstrip("/")
            if len(path) > 40:
                path = f"{path[:37]}…"
            return f"{parsed.netloc}{path}"
        except Exception:
            return url[:60]

    def _persist_extracted(self, extracted: ExtractedJob) -> Job:
        url = normalize_job_url(extracted.url)
        if not url:
            raise DomainError("Job URL is required")

        existing = self._session.query(Job).filter(Job.url == url).one_or_none()
        if existing is not None:
            self._ensure_match(existing.id)
            return existing

        fingerprint = job_fingerprint(extracted)
        if extracted.external_id:
            by_ext = (
                self._session.query(Job)
                .filter(Job.external_id == extracted.external_id)
                .one_or_none()
            )
            if by_ext is not None:
                self._ensure_match(by_ext.id)
                return by_ext

        company = self._get_or_create_company(extracted.company_name)
        details = extracted.model_dump(mode="json")
        details["fingerprint"] = fingerprint
        job = Job(
            id=uuid.uuid4(),
            company_id=company.id,
            status=JobStatus.active,
            title=extracted.title,
            url=url,
            external_id=extracted.external_id or fingerprint,
            description=extracted.description,
            details=details,
        )
        try:
            with self._session.begin_nested():
                self._session.add(job)
                self._session.flush()
        except IntegrityError:
            existing = (
                self._session.query(Job).filter(Job.url == url).one_or_none()
                or self._session.query(Job)
                .filter(Job.external_id == (extracted.external_id or fingerprint))
                .one_or_none()
            )
            if existing is None:
                raise DomainError("Failed to persist job due to conflict") from None
            self._ensure_match(existing.id)
            return existing

        self._ensure_match(job.id)
        return job

    def _get_or_create_company(self, name: str | None) -> Company:
        cleaned = (name or "").strip() or "Unknown Company"
        existing = (
            self._session.query(Company)
            .filter(Company.name == cleaned)
            .order_by(Company.created_at.asc())
            .first()
        )
        if existing is not None:
            return existing
        company = Company(id=uuid.uuid4(), name=cleaned, status=CompanyStatus.active)
        self._session.add(company)
        self._session.flush()
        return company

    def _ensure_match(self, job_id: uuid.UUID) -> JobMatch:
        row = (
            self._session.query(JobMatch)
            .filter(JobMatch.user_id == self._user_id, JobMatch.job_id == job_id)
            .one_or_none()
        )
        if row is not None:
            return row
        row = JobMatch(
            id=uuid.uuid4(),
            user_id=self._user_id,
            job_id=job_id,
            status=JobMatchStatus.new,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def _start_task(self, run_id: uuid.UUID, task_type: str, payload: dict) -> WorkflowTask:
        task = WorkflowTask(
            id=uuid.uuid4(),
            user_id=self._user_id,
            workflow_run_id=run_id,
            status=WorkflowTaskStatus.running,
            task_type=task_type,
            input_payload=payload,
            attempt=1,
        )
        self._session.add(task)
        self._session.flush()
        self._publish_progress(
            run_id=run_id,
            step=task_type,
            phase="working",
            message=f"Running {task_type}…",
            data={"task_id": str(task.id), "input": payload, "status": "running"},
        )
        return task

    def _complete_task(self, task: WorkflowTask, output: dict) -> None:
        task.status = WorkflowTaskStatus.completed
        task.output_payload = output
        self._session.flush()
        self._publish_progress(
            run_id=task.workflow_run_id,
            step=task.task_type,
            phase="result",
            message=f"Completed {task.task_type}.",
            data={"task_id": str(task.id), "output": output, "status": "completed"},
        )

    def _fail_task(self, task: WorkflowTask, error: str) -> None:
        task.status = WorkflowTaskStatus.failed
        task.error = error
        self._session.flush()
        self._publish_progress(
            run_id=task.workflow_run_id,
            step=task.task_type,
            phase="error",
            message=f"Failed {task.task_type}: {error}",
            data={"task_id": str(task.id), "error": error, "status": "failed"},
        )

    def _update_run_metadata(
        self,
        run: WorkflowRun,
        *,
        current_step: str,
        message: str,
        **extra: object,
    ) -> None:
        metadata = dict(run.metadata_json or {})
        metadata["current_step"] = current_step
        metadata["status_message"] = message
        metadata.update(extra)
        run.metadata_json = metadata
        self._session.flush()
        self._publish_progress(
            run_id=run.id,
            step=current_step,
            phase="thinking",
            message=message,
            data=dict(extra),
        )

    def _publish(self, event_type: UserEventType, payload: dict) -> None:
        if self._events is None:
            return
        self._events.publish(self._user_id, event_type, payload)

    def _publish_progress(
        self,
        *,
        run_id: uuid.UUID,
        step: str,
        message: str,
        phase: str = "working",
        data: dict | None = None,
    ) -> None:
        payload_data = dict(data or {})
        payload_data.setdefault("phase", phase)
        self._publish(
            UserEventType.workflow_progress,
            {
                "workflow_run_id": str(run_id),
                "workflow_type": "job_discovery",
                "step": step,
                "phase": phase,
                "message": message,
                "data": payload_data,
            },
        )


def _build_queries(prefs: PreferenceSettings) -> list[str]:
    roles = prefs.target_roles or ["software engineer"]
    locations = prefs.locations or ["remote"]
    queries: list[str] = []
    for role in roles[:3]:
        for location in locations[:2]:
            queries.append(f"{role} jobs {location}")
    return queries or ["software engineer jobs"]


def normalize_job_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        return raw.rstrip("/")
    # Drop fragments and common tracking query noise for idempotency.
    path = parsed.path.rstrip("/") or ""
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", "", ""))


def job_fingerprint(job: ExtractedJob) -> str:
    basis = "|".join(
        [
            normalize_job_url(job.url),
            (job.title or "").strip().lower(),
            (job.company_name or "").strip().lower(),
        ]
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32]
