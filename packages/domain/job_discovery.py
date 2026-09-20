"""Job discovery: preferences → search → scrape → extract → normalize → persist.

Uses provider interfaces only. Idempotent on job URL / external_id.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
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
from packages.domain.discovery_lock import DiscoveryLock
from packages.domain.discovery_logger import DiscoveryRunLogger
from packages.domain.exceptions import DiscoveryCancelledError, DomainError, NotFoundError
from packages.domain.extraction_constants import extraction_prefilter_max_chars_for_provider
from packages.domain.events import UserEventPublisher, UserEventType
from packages.domain.job_match import JobMatchService
from packages.domain.job_urls import is_likely_listing_page
from packages.domain.workflow_cancellation import WorkflowCancellation
from packages.providers.base import UsageInfo
from packages.providers.exceptions import ProviderError
from packages.domain.job_models import ExtractedJob
from packages.domain.job_normalize import normalize_job_posting, persist_structured_job, structured_to_extracted
from packages.domain.job_posting import StructuredJobPosting
from packages.domain.jobs import load_resume_skills
from packages.domain.llm_tasks import LLMTaskService
from packages.domain.provider_usage import (
    ProviderQuotaLimits,
    ProviderUsageContext,
    ProviderUsageService,
)
from packages.domain.preferences import PreferenceSettings, PreferencesService
from packages.providers.llm import LLMProvider
from packages.providers.playwright_jobs import (
    MockPlaywrightJobsProvider,
    PlaywrightJobsProvider,
    is_known_job_board,
)
from packages.providers.scraper import ScrapeRequest, ScraperProvider
from packages.providers.search import SearchProvider, SearchRequest
from packages.providers.usage_logging import call_with_usage_log

logger = logging.getLogger("career.fetch")


@dataclass
class DiscoveryResult:
    workflow_run_id: uuid.UUID
    created_jobs: list[uuid.UUID] = field(default_factory=list)
    duplicate_jobs: list[uuid.UUID] = field(default_factory=list)
    skipped_invalid: int = 0
    errors: list[str] = field(default_factory=list)
    scrapes_fresh: int = 0
    scrapes_cached: int = 0


DEFAULT_SCRAPE_FRESHNESS_DAYS = 14


class JobDiscoveryService:
    """Discover and ingest jobs for one tenant using live or injected providers."""

    def __init__(
        self,
        session: Session,
        user_id: uuid.UUID,
        *,
        search: SearchProvider,
        scraper: ScraperProvider,
        llm: LLMProvider,
        extraction_llm: LLMProvider | None = None,
        playwright_jobs: PlaywrightJobsProvider | MockPlaywrightJobsProvider | None = None,
        max_results: int = 5,
        events: UserEventPublisher | None = None,
        cancellation: WorkflowCancellation | None = None,
        discovery_lock: DiscoveryLock | None = None,
        scrape_freshness_days: int = DEFAULT_SCRAPE_FRESHNESS_DAYS,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._search = search
        self._scraper = scraper
        self._llm = llm
        self._extraction_llm = extraction_llm or llm
        self._playwright_jobs = playwright_jobs
        self._llm_tasks = LLMTaskService(llm, extraction_llm=self._extraction_llm)
        self._max_results = max_results
        self._events = events
        self._cancellation = cancellation
        self._discovery_lock = discovery_lock
        self._scrape_freshness_days = scrape_freshness_days
        self._url_context: dict[str, dict[str, str]] = {}
        self._file_log: DiscoveryRunLogger | None = None
        self._current_run_id: uuid.UUID | None = None
        self._usage = ProviderUsageService(session)
        self._run_status: str = "running"

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
            if run.status in (
                WorkflowRunStatus.cancelled,
                WorkflowRunStatus.cancelling,
            ) or (
                self._cancellation is not None and self._cancellation.is_cancelled(run.id)
            ):
                run.status = WorkflowRunStatus.cancelled
                metadata = dict(run.metadata_json or {})
                metadata["current_step"] = "cancelled"
                metadata["status_message"] = "Discovery cancelled"
                metadata.setdefault(
                    "cancelled_at", datetime.now(timezone.utc).isoformat()
                )
                run.metadata_json = metadata
                self._session.commit()
                if self._discovery_lock is not None:
                    self._discovery_lock.release(self._user_id)
                if self._cancellation is not None:
                    self._cancellation.clear(run.id)
                return DiscoveryResult(workflow_run_id=run.id)
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
        self._current_run_id = run.id
        self._run_status = "running"
        self._file_log = DiscoveryRunLogger(run.id, workflow_type="job_discovery")
        self._llm_tasks = LLMTaskService(
            self._llm,
            extraction_llm=self._extraction_llm,
            discovery_log=self._file_log,
            usage_service=ProviderUsageService(self._session),
            usage_context=ProviderUsageContext(
                user_id=self._user_id,
                workflow_run_id=run.id,
            ),
        )
        self._file_log.config = self._build_run_config()
        self._file_log.knobs_touched = self._knobs_touched()
        self._file_log.log(
            "run_started",
            user_id=str(self._user_id),
            max_results=self._max_results,
            config=self._file_log.config,
        )
        try:
            queries = _build_queries(prefs)
            self._file_log.queries = list(queries)
            self._file_log.log(
                "queries_planned",
                queries=queries,
                derivation="roles[:3] x locations[:2] → '{role} jobs {location}'",
            )
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
            self._run_status = "completed"
            self._file_log.counts["created"] = len(result.created_jobs)
            self._file_log.counts["duplicates"] = len(result.duplicate_jobs)
            self._file_log.counts["skipped_invalid"] = result.skipped_invalid
            self._file_log.errors = list(result.errors)
            self._file_log.log(
                "run_completed",
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
            self._run_status = "cancelled"
            self._file_log.errors = list(result.errors)
            self._file_log.log("run_cancelled", errors=result.errors)
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
            self._run_status = "failed"
            self._file_log.errors = list(result.errors) + [str(exc)]
            self._file_log.log("run_failed", error=str(exc), errors=result.errors)
            raise
        finally:
            if self._file_log is not None:
                self._file_log.write_summary(
                    status=self._run_status,
                    usage=self._usage_rollup(run.id),
                )
            if self._discovery_lock is not None:
                self._discovery_lock.release(self._user_id)
            if self._cancellation is not None and self._current_run_id is not None:
                self._cancellation.clear(self._current_run_id)
        return result

    def _build_run_config(self) -> dict:
        limits = ProviderQuotaLimits()
        return {
            "search_provider": self._search.metadata.name,
            "scraper_provider": self._scraper.metadata.name,
            "llm_provider": self._llm.metadata.name,
            "extraction_llm_provider": self._extraction_llm.metadata.name,
            "playwright_jobs_provider": (
                self._playwright_jobs.metadata.name if self._playwright_jobs else None
            ),
            "max_results": self._max_results,
            "scrape_freshness_days": self._scrape_freshness_days,
            "prompt_version": self._llm_tasks.prompt_version,
            "quota_limits": limits.model_dump(),
            "bodies_enabled": self._file_log.bodies_enabled if self._file_log else False,
            "snippet_chars": self._file_log.snippet_chars if self._file_log else 500,
        }

    @staticmethod
    def _knobs_touched() -> list[str]:
        import os

        knobs = [
            "max_results",
            "LLM_PROVIDER",
            "GROQ_MODEL",
            "GEMINI_MODEL",
            "GEMINI_EXTRACTION_MODEL",
            "GEMINI_TIER",
            "OPENAI_MODEL",
            "EXTRACTION_LLM_PROVIDER",
            "EXTRACTION_LLM_MODEL",
            "TAVILY_API_KEY",
            "FIRECRAWL_BASE_URL",
            "FIRECRAWL_API_KEY",
            "DISCOVERY_LOG_BODIES",
            "DISCOVERY_LOG_SNIPPET_CHARS",
        ]
        present = []
        for key in knobs:
            if key == "max_results":
                present.append(key)
            elif key.endswith("_API_KEY"):
                if os.getenv(key, "").strip():
                    present.append(f"{key}=set")
            elif os.getenv(key, "").strip():
                present.append(key)
        return present

    def _usage_rollup(self, run_id: uuid.UUID) -> dict:
        return self._usage.summarize_workflow_run(
            workflow_run_id=run_id,
            user_id=self._user_id,
        )

    def _ensure_not_cancelled(self, run: WorkflowRun) -> None:
        self._session.refresh(run)
        if run.status in (WorkflowRunStatus.cancelled, WorkflowRunStatus.cancelling):
            if run.status == WorkflowRunStatus.cancelling:
                run.status = WorkflowRunStatus.cancelled
                metadata = dict(run.metadata_json or {})
                metadata["cancelled_at"] = datetime.now(timezone.utc).isoformat()
                run.metadata_json = metadata
                self._session.flush()
            raise DiscoveryCancelledError("Discovery cancelled by user")
        if self._cancellation is not None and self._cancellation.is_cancelled(run.id):
            run.status = WorkflowRunStatus.cancelled
            metadata = dict(run.metadata_json or {})
            metadata["cancelled_at"] = datetime.now(timezone.utc).isoformat()
            run.metadata_json = metadata
            self._session.flush()
            raise DiscoveryCancelledError("Discovery cancelled by user")

    def _score_discovered_jobs(
        self, result: DiscoveryResult, prefs: PreferenceSettings
    ) -> None:
        job_ids = list(dict.fromkeys(result.created_jobs + result.duplicate_jobs))
        if not job_ids:
            return
        if self._file_log is not None:
            self._file_log.log("score_started", job_count=len(job_ids))
        resume_skills = load_resume_skills(self._session, self._user_id)
        matcher = JobMatchService(self._session, self._user_id)
        for job_id in job_ids:
            run = (
                self._session.query(WorkflowRun)
                .filter(WorkflowRun.id == self._current_run_id)
                .one_or_none()
            )
            if run is not None:
                self._ensure_not_cancelled(run)
            match = matcher.upsert_match(job_id, preferences=prefs, resume_skills=resume_skills)
            if self._file_log is not None:
                score = getattr(match, "score", None)
                self._file_log.log(
                    "score_job",
                    job_id=str(job_id),
                    score=score,
                )
        if self._file_log is not None:
            self._file_log.log("score_completed", job_count=len(job_ids))

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
            if self._file_log is not None:
                self._file_log.bump("search_calls")
                self._file_log.log(
                    "search_request",
                    provider=provider,
                    query=query,
                    max_results=self._max_results,
                )
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
                            if self._file_log is not None:
                                self._file_log.bump("urls_skipped")
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
                if self._file_log is not None:
                    self._file_log.bump("urls_found", len(found))
                    self._file_log.log(
                        "search_result",
                        provider=provider,
                        query=query,
                        hits=len(response.results),
                        accepted=len(found),
                        urls=found,
                        usage_units=getattr(response.usage, "units", None),
                    )
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
                if self._file_log is not None:
                    self._file_log.log(
                        "search_failed",
                        provider=provider,
                        query=query,
                        error=str(exc),
                    )
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
            if self._file_log is not None:
                self._file_log.bump("urls_skipped")
                self._file_log.log("url_skipped", url=url, reason="listing_page")
            result.skipped_invalid += 1
            return

        existing = self._find_existing_job(url)
        if existing is not None and self._is_scrape_fresh(existing):
            self._ensure_match(existing.id)
            result.duplicate_jobs.append(existing.id)
            result.scrapes_cached += 1
            self._record_scrape_usage(run_id, cached=True)
            if self._file_log is not None:
                self._file_log.bump("duplicates")
                self._file_log.log(
                    "scrape_fresh_hit",
                    url=url,
                    job_id=str(existing.id),
                    reason="fresh_cache",
                )
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

            # Tiered scrape: Playwright (known boards) → Firecrawl one-off → LLM on cleaned schema only.
            if self._file_log is not None:
                self._file_log.log("scrape_request", url=url, provider=scrape_provider)
            structured = self._try_structured_scrape(url, run_id)
            if structured is not None:
                job = persist_structured_job(
                    self._session,
                    structured,
                    user_id=self._user_id,
                    run_id=run_id,
                )
                extracted = structured_to_extracted(structured)
                content_source = structured.source
                result.scrapes_fresh += 1
                result.created_jobs.append(job.id)
                if self._file_log is not None:
                    self._file_log.bump("scrapes")
                    self._file_log.bump("created")
                    self._file_log.log(
                        "scrape_result",
                        url=url,
                        content_source=content_source,
                        chars=len(structured.description or "") + len(structured.title or ""),
                    )
                    self._file_log.log(
                        "job_created",
                        url=url,
                        job_id=str(job.id),
                        title=job.title,
                        company=extracted.company_name,
                        content_source=content_source,
                    )
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
                return

            markdown, content_source = self._scrape_markdown(url, run_id)
            from packages.shared.security import sanitize_scraped_content, validate_public_url

            try:
                validate_public_url(url)
            except Exception as exc:
                raise DomainError(f"Blocked URL: {exc}") from exc
            guarded = sanitize_scraped_content(markdown)
            markdown = guarded.safe_text
            if self._file_log is not None:
                self._file_log.bump("scrapes")
                scrape_fields = {
                    "url": url,
                    "content_source": content_source,
                    "chars": len(markdown),
                    "injection_flagged": guarded.flagged,
                }
                scrape_fields.update(
                    self._file_log.payload_fields(
                        text=markdown,
                        snippet_key="scraped_snippet",
                        body_key="scraped_markdown",
                    )
                )
                self._file_log.log("scrape_result", **scrape_fields)
            prefilter_limit = extraction_prefilter_max_chars_for_provider(
                self._extraction_llm.metadata.name
            )
            if content_source == "scrape" and len(markdown) > prefilter_limit:
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
            run = (
                self._session.query(WorkflowRun)
                .filter(WorkflowRun.id == run_id)
                .one()
            )
            self._ensure_not_cancelled(run)
            # Pass cleaned prose only — never raw HTML/DOM to the LLM.
            extracted = self._llm_tasks.extract_job(
                url=url,
                scraped_markdown=markdown,
            )
            if self._file_log is not None:
                self._file_log.bump("extracts")
                self._file_log.log(
                    "extract_success",
                    url=url,
                    title=extracted.title,
                    company=extracted.company_name,
                )
            job = self._persist_extracted(extracted, run_id=run_id, existing=existing)
            if content_source == "scrape":
                result.scrapes_fresh += 1
                self._record_scrape_usage(run_id, cached=False)
            result.created_jobs.append(job.id)
            if self._file_log is not None:
                self._file_log.bump("created")
                self._file_log.log(
                    "job_created",
                    url=url,
                    job_id=str(job.id),
                    title=job.title,
                    company=extracted.company_name,
                    content_source=content_source,
                )
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
            if self._file_log is not None:
                self._file_log.bump("skipped_invalid")
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
            if self._file_log is not None:
                self._file_log.log("ingest_failed", url=url, error=str(exc))

    def _try_structured_scrape(
        self,
        url: str,
        run_id: uuid.UUID,
    ) -> StructuredJobPosting | None:
        """Playwright for known boards; Firecrawl structured extract for one-offs only."""
        context = ProviderUsageContext(user_id=self._user_id, workflow_run_id=run_id)

        if self._playwright_jobs is not None and (
            self._playwright_jobs.can_handle(url) or is_known_job_board(url)
        ):
            try:
                result = call_with_usage_log(
                    self._usage,
                    context=context,
                    provider=self._playwright_jobs.metadata.name,
                    operation="job_extraction",
                    fn=lambda: self._playwright_jobs.scrape_job(url),
                    usage_from_result=lambda r: r.usage,
                )
                return normalize_job_posting(result.posting)
            except Exception as exc:
                logger.warning("PLAYWRIGHT_JOBS_FAILED url=%s error=%s", url, exc)
                if is_known_job_board(url):
                    # Known boards must not fall through to Firecrawl.
                    return None

        if is_known_job_board(url):
            return None

        extract_fn = getattr(self._scraper, "extract_structured_job", None)
        if extract_fn is None:
            return None
        try:
            raw, usage = call_with_usage_log(
                self._usage,
                context=context,
                provider=self._scraper.metadata.name,
                operation="job_extraction",
                fn=lambda: extract_fn(url),
                usage_from_result=lambda pair: pair[1],
            )
            raw = dict(raw)
            raw.setdefault("source", "firecrawl")
            raw.setdefault("application_url", url)
            if "scraped_at" not in raw:
                raw["scraped_at"] = datetime.now(timezone.utc).isoformat()
            if not raw.get("external_job_id"):
                raw["external_job_id"] = job_fingerprint_from_url(url)
            return normalize_job_posting(raw)
        except Exception as exc:
            logger.warning("FIRECRAWL_STRUCTURED_FAILED url=%s error=%s", url, exc)
            return None

    def _scrape_markdown(self, url: str, run_id: uuid.UUID) -> tuple[str, str]:
        run = (
            self._session.query(WorkflowRun)
            .filter(WorkflowRun.id == run_id)
            .one()
        )
        self._ensure_not_cancelled(run)
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
            if self._file_log is not None:
                self._file_log.bump("scrape_failures")
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

    def _persist_extracted(
        self,
        extracted: ExtractedJob,
        *,
        run_id: uuid.UUID | None = None,
        existing: Job | None = None,
    ) -> Job:
        url = normalize_job_url(extracted.url)
        if not url:
            raise DomainError("Job URL is required")

        now = datetime.now(timezone.utc)
        fingerprint = job_fingerprint(extracted)

        if existing is None:
            existing = self._session.query(Job).filter(Job.url == url).one_or_none()
        if existing is None:
            existing = self._find_job_by_fingerprint(fingerprint)

        if existing is not None:
            company = self._get_or_create_company(extracted.company_name)
            details = extracted.model_dump(mode="json")
            details["fingerprint"] = fingerprint
            existing.title = extracted.title or existing.title
            existing.description = extracted.description or existing.description
            existing.company_id = company.id
            existing.details = details
            existing.last_scraped_at = now
            existing.scraped_at = now
            if extracted.skills:
                existing.skills = list(extracted.skills)
            if extracted.work_arrangement:
                existing.remote_type = (
                    "onsite" if extracted.work_arrangement == "on_site" else extracted.work_arrangement
                )
            if extracted.employment_type:
                existing.employment_type = extracted.employment_type
            if extracted.seniority:
                existing.seniority = extracted.seniority
            if extracted.salary_min is not None:
                existing.salary_min = extracted.salary_min
            if extracted.salary_max is not None:
                existing.salary_max = extracted.salary_max
            if extracted.currency:
                existing.salary_currency = extracted.currency
            if run_id is not None:
                existing.discovery_run_id = run_id
            self._session.flush()
            self._ensure_match(existing.id)
            return existing

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
        remote = None
        if extracted.work_arrangement == "on_site":
            remote = "onsite"
        elif extracted.work_arrangement in ("remote", "hybrid"):
            remote = extracted.work_arrangement
        job = Job(
            id=uuid.uuid4(),
            company_id=company.id,
            status=JobStatus.active,
            title=extracted.title,
            url=url,
            external_id=extracted.external_id or fingerprint,
            source="llm_extract",
            description=extracted.description,
            details=details,
            skills=list(extracted.skills) or None,
            remote_type=remote,
            employment_type=extracted.employment_type,
            seniority=extracted.seniority,
            salary_min=extracted.salary_min,
            salary_max=extracted.salary_max,
            salary_currency=extracted.currency,
            last_scraped_at=now,
            scraped_at=now,
            discovery_run_id=run_id,
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

    def _find_existing_job(self, url: str) -> Job | None:
        normalized = normalize_job_url(url)
        row = self._session.query(Job).filter(Job.url == normalized).one_or_none()
        return row

    def _find_job_by_fingerprint(self, fingerprint: str) -> Job | None:
        rows = self._session.query(Job).all()
        for row in rows:
            details = row.details if isinstance(row.details, dict) else {}
            if details.get("fingerprint") == fingerprint:
                return row
        return None

    def _is_scrape_fresh(self, job: Job) -> bool:
        if job.last_scraped_at is None:
            return False
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._scrape_freshness_days)
        scraped_at = job.last_scraped_at
        if scraped_at.tzinfo is None:
            scraped_at = scraped_at.replace(tzinfo=timezone.utc)
        return scraped_at >= cutoff

    def _record_scrape_usage(self, run_id: uuid.UUID, *, cached: bool) -> None:
        usage = ProviderUsageService(self._session)
        usage.record(
            context=ProviderUsageContext(
                user_id=self._user_id,
                workflow_run_id=run_id,
            ),
            provider_name=self._scraper.metadata.name,
            operation="scrape_cached" if cached else "scrape",
            usage=UsageInfo(
                operation="scrape_cached" if cached else "scrape",
                unit_type="requests",
                units=1.0,
                extra={"cached": cached},
            ),
            success=True,
        )

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


def job_fingerprint_from_url(url: str) -> str:
    return hashlib.sha256(normalize_job_url(url).encode("utf-8")).hexdigest()[:32]
