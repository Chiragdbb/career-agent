"""Job discovery: preferences → search → scrape → extract → normalize → persist.

Uses provider interfaces only. Idempotent on job URL / external_id.
"""

from __future__ import annotations

import hashlib
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
from packages.domain.exceptions import DomainError, NotFoundError
from packages.domain.job_match import JobMatchService
from packages.domain.job_models import ExtractedJob
from packages.domain.jobs import load_resume_skills
from packages.domain.llm_tasks import LLMTaskService
from packages.domain.preferences import PreferenceSettings, PreferencesService
from packages.providers.llm import LLMProvider
from packages.providers.scraper import ScrapeRequest, ScraperProvider
from packages.providers.search import SearchProvider, SearchRequest


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
        max_results: int = 5,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._search = search
        self._scraper = scraper
        self._llm_tasks = LLMTaskService(llm)
        self._max_results = max_results

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
            run.metadata_json = metadata
            self._session.flush()
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
        try:
            queries = _build_queries(prefs)
            urls = self._search_urls(queries, run.id, result)
            for url in urls:
                self._ingest_url(url, run.id, result)
            self._score_discovered_jobs(result, prefs)
            run.status = WorkflowRunStatus.completed
            self._session.commit()
        except Exception as exc:
            run.status = WorkflowRunStatus.failed
            run.error = str(exc)
            self._session.commit()
            raise
        return result

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
            task = self._start_task(run_id, "search", {"query": query})
            try:
                response = self._search.search(
                    SearchRequest(query=query, max_results=self._max_results)
                )
                found = []
                for hit in response.results:
                    normalized = normalize_job_url(str(hit.url))
                    if normalized and normalized not in seen:
                        seen.add(normalized)
                        ordered.append(normalized)
                        found.append(normalized)
                self._complete_task(task, {"urls": found})
            except Exception as exc:
                self._fail_task(task, str(exc))
                result.errors.append(f"search:{query}:{exc}")
        return ordered

    def _ingest_url(self, url: str, run_id: uuid.UUID, result: DiscoveryResult) -> None:
        existing = self._session.query(Job).filter(Job.url == url).one_or_none()
        if existing is not None:
            self._ensure_match(existing.id)
            result.duplicate_jobs.append(existing.id)
            return

        task = self._start_task(run_id, "ingest_url", {"url": url})
        try:
            scraped = self._scraper.scrape_url(ScrapeRequest(url=url))
            # Untrusted scraped content — only passed into LLM extract with system guard.
            extracted = self._llm_tasks.extract_job(
                url=url,
                scraped_markdown=scraped.markdown or scraped.title or "",
            )
            job = self._persist_extracted(extracted)
            result.created_jobs.append(job.id)
            self._complete_task(
                task,
                {"job_id": str(job.id), "title": job.title, "company_id": str(job.company_id)},
            )
        except DomainError as exc:
            result.skipped_invalid += 1
            self._fail_task(task, str(exc))
            result.errors.append(f"ingest:{url}:{exc}")
        except Exception as exc:
            self._fail_task(task, str(exc))
            result.errors.append(f"ingest:{url}:{exc}")

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
        return task

    def _complete_task(self, task: WorkflowTask, output: dict) -> None:
        task.status = WorkflowTaskStatus.completed
        task.output_payload = output

    def _fail_task(self, task: WorkflowTask, error: str) -> None:
        task.status = WorkflowTaskStatus.failed
        task.error = error


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
