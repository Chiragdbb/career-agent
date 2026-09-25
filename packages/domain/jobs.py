"""Tenant-scoped job listing, discovery triggers, and match detail."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from database.models.enums import JobMatchStatus, ResumeVersionStatus, WorkflowRunStatus
from database.models.schema import Company, Job, JobMatch, Resume, ResumeVersion, WorkflowRun
from packages.domain.discovery_lock import DiscoveryLock
from packages.domain.exceptions import ConflictError, DomainError, NotFoundError
from packages.domain.job_match import JobMatchService, ScoreBreakdown, format_fit_summary
from packages.domain.preferences import PreferencesService
from packages.domain.resume_models import StructuredResume
from packages.domain.skill_aliases import find_known_skills_in_text
from packages.domain.skill_match import SkillMatchService, skills_match_fuzzy
from packages.domain.workflow_cancellation import WorkflowCancellation


@dataclass(frozen=True)
class JobMatchSummary:
    id: uuid.UUID
    job_id: uuid.UUID
    status: str
    score: float | None
    title: str
    company_name: str | None
    location: str | None
    work_arrangement: str | None
    url: str | None
    is_new: bool = False


@dataclass(frozen=True)
class JobMatchDetail:
    id: uuid.UUID
    job_id: uuid.UUID
    status: str
    score: float | None
    title: str
    company_name: str | None
    location: str | None
    work_arrangement: str | None
    url: str | None
    description: str | None
    job_skills: list[str]
    matched_skills: list[str]
    possible_matches: list[str]
    missing_skills: list[str]
    score_breakdown: ScoreBreakdown | None
    explanation: str | None
    created_at: datetime | None
    # Full listing fields (always present; null/empty when unknown)
    company_domain: str | None = None
    source: str | None = None
    external_id: str | None = None
    employment_type: str | None = None
    remote_type: str | None = None
    seniority: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    requirements: list[str] | None = None
    posted_at: datetime | None = None
    last_scraped_at: datetime | None = None
    scraped_at: datetime | None = None
    job_status: str | None = None


@dataclass(frozen=True)
class DiscoveryEnqueueResult:
    workflow_run_id: uuid.UUID
    status: str
    idempotency_key: str | None


class JobListingService:
    """Read and score tenant job matches with joined job/company data."""

    def __init__(self, session: Session, user_id: uuid.UUID) -> None:
        self._session = session
        self._user_id = user_id

    def list_matches(self, *, include_dismissed: bool = False) -> list[JobMatchSummary]:
        latest_run = self._latest_completed_discovery_run()
        last_seen = self._last_seen_discovery_run_id()
        is_new_run = (
            latest_run is not None
            and (last_seen is None or last_seen != latest_run.id)
        )
        if latest_run is not None:
            self._record_jobs_viewed(latest_run.id)

        query = (
            self._session.query(JobMatch, Job, Company)
            .join(Job, Job.id == JobMatch.job_id)
            .join(Company, Company.id == Job.company_id)
            .filter(JobMatch.user_id == self._user_id)
        )
        if not include_dismissed:
            query = query.filter(JobMatch.status != JobMatchStatus.dismissed)
        rows = query.order_by(
            JobMatch.score.desc().nullslast(), JobMatch.created_at.desc()
        ).all()
        return [
            self._to_summary(
                match,
                job,
                company,
                latest_run_id=latest_run.id if is_new_run and latest_run else None,
            )
            for match, job, company in rows
        ]

    def _latest_completed_discovery_run(self) -> WorkflowRun | None:
        return (
            self._session.query(WorkflowRun)
            .filter(
                WorkflowRun.user_id == self._user_id,
                WorkflowRun.workflow_type == "job_discovery",
                WorkflowRun.status == WorkflowRunStatus.completed,
            )
            .order_by(WorkflowRun.updated_at.desc())
            .first()
        )

    def _last_seen_discovery_run_id(self) -> uuid.UUID | None:
        row = PreferencesService(self._session, self._user_id).get_or_create()
        settings = row.settings if isinstance(row.settings, dict) else {}
        raw = settings.get("last_seen_discovery_run_id")
        if not raw:
            return None
        try:
            return uuid.UUID(str(raw))
        except ValueError:
            return None

    def _record_jobs_viewed(self, run_id: uuid.UUID) -> None:
        """Persist that the user opened /jobs so 'New' badges clear on the next visit."""
        row = PreferencesService(self._session, self._user_id).get_or_create()
        settings = dict(row.settings or {})
        settings["last_seen_discovery_run_id"] = str(run_id)
        row.settings = settings
        self._session.commit()

    def update_match_status(self, match_id: uuid.UUID, status: JobMatchStatus) -> JobMatchSummary:
        row = (
            self._session.query(JobMatch, Job, Company)
            .join(Job, Job.id == JobMatch.job_id)
            .join(Company, Company.id == Job.company_id)
            .filter(JobMatch.id == match_id, JobMatch.user_id == self._user_id)
            .one_or_none()
        )
        if row is None:
            raise NotFoundError("Job not found")
        match, job, company = row
        match.status = status
        self._session.commit()
        self._session.refresh(match)
        return self._to_summary(match, job, company)

    def bulk_update_status(
        self, match_ids: list[uuid.UUID], status: JobMatchStatus
    ) -> list[JobMatchSummary]:
        if not match_ids:
            return []
        matches = (
            self._session.query(JobMatch)
            .filter(
                JobMatch.user_id == self._user_id,
                JobMatch.id.in_(match_ids),
            )
            .all()
        )
        if len(matches) != len(set(match_ids)):
            raise NotFoundError("One or more jobs not found")
        for match in matches:
            match.status = status
        self._session.commit()
        updated_ids = {match.id for match in matches}
        return [
            summary
            for summary in self.list_matches(include_dismissed=True)
            if summary.id in updated_ids
        ]

    def get_match_detail(self, match_id: uuid.UUID) -> JobMatchDetail:
        row = (
            self._session.query(JobMatch, Job, Company)
            .join(Job, Job.id == JobMatch.job_id)
            .join(Company, Company.id == Job.company_id)
            .filter(JobMatch.id == match_id, JobMatch.user_id == self._user_id)
            .one_or_none()
        )
        if row is None:
            raise NotFoundError("Job not found")
        match, job, company = row
        resume_skills = load_resume_skills(self._session, self._user_id)
        prefs = PreferencesService(self._session, self._user_id).get_settings()
        breakdown = JobMatchService(self._session, self._user_id).score_job(
            job,
            prefs,
            company_name=company.name if company else None,
            resume_skills=resume_skills,
        )
        job_skills = _job_skills(job)
        live = SkillMatchService().align(job_skills, resume_skills)
        matched = live.matched
        possible = live.possible
        missing = live.missing
        return self._to_detail(
            match,
            job,
            company,
            breakdown=breakdown,
            matched_skills=matched,
            possible_matches=possible,
            missing_skills=missing,
        )

    def rescore_match(self, match_id: uuid.UUID) -> JobMatchDetail:
        match = (
            self._session.query(JobMatch)
            .filter(JobMatch.id == match_id, JobMatch.user_id == self._user_id)
            .one_or_none()
        )
        if match is None:
            raise NotFoundError("Job not found")
        resume_skills = load_resume_skills(self._session, self._user_id)
        JobMatchService(self._session, self._user_id).upsert_match(
            match.job_id,
            resume_skills=resume_skills,
        )
        return self.get_match_detail(match_id)

    def _to_summary(
        self,
        match: JobMatch,
        job: Job,
        company: Company,
        *,
        latest_run_id: uuid.UUID | None = None,
    ) -> JobMatchSummary:
        details = job.details if isinstance(job.details, dict) else {}
        is_new = (
            latest_run_id is not None
            and job.discovery_run_id is not None
            and job.discovery_run_id == latest_run_id
        )
        return JobMatchSummary(
            id=match.id,
            job_id=match.job_id,
            status=match.status.value if hasattr(match.status, "value") else str(match.status),
            score=match.score,
            title=job.title,
            company_name=company.name if company else None,
            location=_as_str(details.get("location")),
            work_arrangement=_as_str(details.get("work_arrangement")),
            url=job.url,
            is_new=is_new,
        )

    def _to_detail(
        self,
        match: JobMatch,
        job: Job,
        company: Company,
        *,
        breakdown: ScoreBreakdown | None,
        matched_skills: list[str],
        possible_matches: list[str],
        missing_skills: list[str],
    ) -> JobMatchDetail:
        details = job.details if isinstance(job.details, dict) else {}
        job_skills = _job_skills(job)
        location = _as_str(details.get("location")) or _as_str(getattr(job, "location", None))
        work_arrangement = (
            _as_str(details.get("work_arrangement"))
            or _as_str(job.remote_type)
        )
        employment_type = _as_str(details.get("employment_type")) or _as_str(job.employment_type)
        seniority = _as_str(details.get("seniority")) or _as_str(job.seniority)
        salary_min = _as_float(details.get("salary_min"))
        if salary_min is None and job.salary_min is not None:
            salary_min = float(job.salary_min)
        salary_max = _as_float(details.get("salary_max"))
        if salary_max is None and job.salary_max is not None:
            salary_max = float(job.salary_max)
        salary_currency = (
            _as_str(details.get("currency"))
            or _as_str(details.get("salary_currency"))
            or _as_str(job.salary_currency)
        )
        requirements = _string_list(details.get("requirements"))
        explanation = format_fit_summary(breakdown) if breakdown is not None else match.fit_summary
        return JobMatchDetail(
            id=match.id,
            job_id=match.job_id,
            status=match.status.value if hasattr(match.status, "value") else str(match.status),
            score=match.score if match.score is not None else (breakdown.total if breakdown else None),
            title=job.title,
            company_name=company.name if company else None,
            location=location,
            work_arrangement=work_arrangement,
            url=job.url,
            description=job.description,
            job_skills=job_skills,
            matched_skills=matched_skills,
            possible_matches=possible_matches,
            missing_skills=missing_skills,
            score_breakdown=breakdown,
            explanation=explanation,
            created_at=match.created_at,
            company_domain=_as_str(job.company_domain) or _as_str(details.get("company_domain")),
            source=_as_str(job.source) or _as_str(details.get("source")),
            external_id=_as_str(job.external_id) or _as_str(details.get("external_id")),
            employment_type=employment_type,
            remote_type=_as_str(job.remote_type) or _as_str(details.get("remote_type")),
            seniority=seniority,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=salary_currency,
            requirements=requirements,
            posted_at=_as_datetime(details.get("posted_at")) or job.posted_at,
            last_scraped_at=job.last_scraped_at,
            scraped_at=job.scraped_at,
            job_status=job.status.value if hasattr(job.status, "value") else str(job.status),
        )


class DiscoveryTriggerService:
    """Create queued workflow runs for async job discovery."""

    ACTIVE_STATUSES = (
        WorkflowRunStatus.queued,
        WorkflowRunStatus.running,
        WorkflowRunStatus.cancelling,
    )

    def __init__(
        self,
        session: Session,
        user_id: uuid.UUID,
        *,
        discovery_lock: DiscoveryLock | None = None,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._discovery_lock = discovery_lock

    def enqueue(
        self,
        *,
        idempotency_key: str | None = None,
        max_results: int = 5,
        discovery_mode: str = "profile",
        query_hint: str | None = None,
    ) -> DiscoveryEnqueueResult:
        if idempotency_key:
            recent = (
                self._session.query(WorkflowRun)
                .filter(
                    WorkflowRun.user_id == self._user_id,
                    WorkflowRun.workflow_type == "job_discovery",
                )
                .order_by(WorkflowRun.created_at.desc())
                .limit(20)
                .all()
            )
            for existing in recent:
                meta = existing.metadata_json if isinstance(existing.metadata_json, dict) else {}
                if meta.get("idempotency_key") == idempotency_key:
                    return DiscoveryEnqueueResult(
                        workflow_run_id=existing.id,
                        status=existing.status.value,
                        idempotency_key=idempotency_key,
                    )

        run_id = uuid.uuid4()
        if self._discovery_lock is not None:
            if not self._discovery_lock.acquire(self._user_id, run_id):
                holder = self._discovery_lock.get_holder(self._user_id)
                if holder is None:
                    active = self._find_active_run()
                    holder = active.id if active is not None else None
                raise ConflictError(
                    "Job discovery already in progress",
                    details={"workflow_run_id": str(holder) if holder else None},
                )

        active = self._find_active_run()
        if active is not None:
            if self._discovery_lock is not None:
                self._discovery_lock.release(self._user_id)
            raise ConflictError(
                "Job discovery already in progress",
                details={"workflow_run_id": str(active.id)},
            )

        run = WorkflowRun(
            id=run_id,
            user_id=self._user_id,
            status=WorkflowRunStatus.queued,
            workflow_type="job_discovery",
            metadata_json={
                "max_results": max_results,
                "idempotency_key": idempotency_key,
                "discovery_mode": discovery_mode if discovery_mode in ("profile", "explore") else "profile",
                "query_hint": (query_hint or "").strip() or None,
                "queued_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        self._session.add(run)
        self._session.commit()
        self._session.refresh(run)
        return DiscoveryEnqueueResult(
            workflow_run_id=run.id,
            status=run.status.value,
            idempotency_key=idempotency_key,
        )

    def _find_active_run(self) -> WorkflowRun | None:
        return (
            self._session.query(WorkflowRun)
            .filter(
                WorkflowRun.user_id == self._user_id,
                WorkflowRun.workflow_type == "job_discovery",
                WorkflowRun.status.in_(self.ACTIVE_STATUSES),
            )
            .first()
        )

    def attach_task_id(self, run_id: uuid.UUID, task_id: str) -> None:
        run = self.get_run(run_id)
        metadata = dict(run.metadata_json or {})
        metadata["task_id"] = task_id
        run.metadata_json = metadata
        self._session.commit()

    def cancel(self, run_id: uuid.UUID, *, cancellation: WorkflowCancellation | None = None) -> WorkflowRun:
        run = self.get_run(run_id)
        if run.status not in self.ACTIVE_STATUSES:
            raise DomainError("Workflow is not active")

        now = datetime.now(timezone.utc).isoformat()
        metadata = dict(run.metadata_json or {})
        metadata["cancel_requested_at"] = now

        # Queued (or stuck cancelling) never had a runner observing the flag — finalize now.
        # Running jobs: mark cancelled immediately for UI, and signal Redis so the worker
        # stops at the next cooperative checkpoint.
        run.status = WorkflowRunStatus.cancelled
        metadata["current_step"] = "cancelled"
        label = (
            "Discovery"
            if run.workflow_type == "job_discovery"
            else format_workflow_label(run.workflow_type)
        )
        metadata["status_message"] = f"{label} cancelled"
        metadata["cancelled_at"] = now
        run.metadata_json = metadata
        run.error = None
        self._session.commit()

        if cancellation is not None:
            cancellation.request_cancel(run_id)
        if self._discovery_lock is not None and run.workflow_type == "job_discovery":
            self._discovery_lock.release(self._user_id)

        self._session.refresh(run)
        return run

    def get_run(self, run_id: uuid.UUID) -> WorkflowRun:
        row = (
            self._session.query(WorkflowRun)
            .filter(
                WorkflowRun.id == run_id,
                WorkflowRun.user_id == self._user_id,
            )
            .one_or_none()
        )
        if row is None:
            raise NotFoundError("Workflow run not found")
        return row


class JobRescrapeTriggerService:
    """Create queued workflow runs for async single-job re-scrape."""

    ACTIVE_STATUSES = DiscoveryTriggerService.ACTIVE_STATUSES

    def __init__(self, session: Session, user_id: uuid.UUID) -> None:
        self._session = session
        self._user_id = user_id

    def enqueue(self, match_id: uuid.UUID) -> DiscoveryEnqueueResult:
        match = (
            self._session.query(JobMatch, Job)
            .join(Job, Job.id == JobMatch.job_id)
            .filter(JobMatch.id == match_id, JobMatch.user_id == self._user_id)
            .one_or_none()
        )
        if match is None:
            raise NotFoundError("Job not found")
        _match, job = match
        if not job.url:
            raise DomainError("Job has no source URL to re-scrape")

        active = (
            self._session.query(WorkflowRun)
            .filter(
                WorkflowRun.user_id == self._user_id,
                WorkflowRun.workflow_type == "job_rescrape",
                WorkflowRun.status.in_(self.ACTIVE_STATUSES),
            )
            .order_by(WorkflowRun.created_at.desc())
            .all()
        )
        for existing in active:
            meta = existing.metadata_json if isinstance(existing.metadata_json, dict) else {}
            if meta.get("match_id") == str(match_id):
                return DiscoveryEnqueueResult(
                    workflow_run_id=existing.id,
                    status=existing.status.value,
                    idempotency_key=None,
                )

        run = WorkflowRun(
            id=uuid.uuid4(),
            user_id=self._user_id,
            status=WorkflowRunStatus.queued,
            workflow_type="job_rescrape",
            metadata_json={
                "match_id": str(match_id),
                "job_id": str(job.id),
                "url": job.url,
                "queued_at": datetime.now(timezone.utc).isoformat(),
                "current_step": "queued",
                "status_message": "Re-scrape queued",
            },
        )
        self._session.add(run)
        self._session.commit()
        self._session.refresh(run)
        return DiscoveryEnqueueResult(
            workflow_run_id=run.id,
            status=run.status.value,
            idempotency_key=None,
        )

    def attach_task_id(self, run_id: uuid.UUID, task_id: str) -> None:
        DiscoveryTriggerService(self._session, self._user_id).attach_task_id(run_id, task_id)


def format_workflow_label(workflow_type: str) -> str:
    return workflow_type.replace("_", " ").strip().capitalize() or "Workflow"


def load_resume_skills(session: Session, user_id: uuid.UUID) -> list[str]:
    """Load skills from the user's most recent finalized resume version.

    Harvests structured skills, project technologies, and known skill phrases
    from summary / experience bullets / plain text so wording differences still match.
    """
    version = (
        session.query(ResumeVersion)
        .join(Resume, Resume.id == ResumeVersion.resume_id)
        .filter(
            Resume.user_id == user_id,
            ResumeVersion.user_id == user_id,
            ResumeVersion.status == ResumeVersionStatus.finalized,
        )
        .order_by(ResumeVersion.created_at.desc())
        .first()
    )
    if version is None:
        return []

    collected: list[str] = []
    seen: set[str] = set()

    def _add(skill: str) -> None:
        cleaned = skill.strip()
        if not cleaned:
            return
        key = cleaned.lower()
        if key in seen:
            return
        seen.add(key)
        collected.append(cleaned)

    structured: StructuredResume | None = None
    if isinstance(version.sections, dict):
        try:
            structured = StructuredResume.model_validate(version.sections)
        except Exception:
            structured = None

    if structured is not None:
        for skill in structured.skills:
            _add(skill)
        for project in structured.projects:
            for tech in project.technologies:
                _add(tech)
        text_parts: list[str] = []
        if structured.summary:
            text_parts.append(structured.summary)
        for exp in structured.experience:
            if exp.title:
                text_parts.append(exp.title)
            if exp.company:
                text_parts.append(exp.company)
            text_parts.extend(exp.bullets)
        for skill in find_known_skills_in_text("\n".join(text_parts)):
            _add(skill)

    if version.plain_text:
        for skill in find_known_skills_in_text(version.plain_text):
            _add(skill)

    return collected


def _skill_alignment_from_match(match: JobMatch) -> dict[str, list[str]] | None:
    raw = match.skill_alignment
    if not isinstance(raw, dict):
        return None
    return {
        "matched": [str(s) for s in raw.get("matched", []) if s],
        "possible": [str(s) for s in raw.get("possible", []) if s],
        "missing": [str(s) for s in raw.get("missing", []) if s],
    }


def align_skills(job_skills: list[str], resume_skills: list[str]) -> tuple[list[str], list[str]]:
    if not job_skills:
        return [], []
    matched: list[str] = []
    missing: list[str] = []
    for skill in job_skills:
        if any(skills_match_fuzzy(skill, resume) for resume in resume_skills):
            matched.append(skill)
        else:
            missing.append(skill)
    return matched, missing


def _job_skills(job: Job) -> list[str]:
    details = job.details if isinstance(job.details, dict) else {}
    raw = details.get("skills") or job.skills or []
    return [str(skill).strip() for skill in raw if isinstance(skill, str) and str(skill).strip()]


def _as_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_datetime(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if isinstance(item, str) and str(item).strip()]


# Re-exports for the tiered scrape contract (spec §2.3).
from packages.domain.job_normalize import (  # noqa: E402
    normalize_job_posting,
    persist_structured_job,
    structured_to_extracted,
)
from packages.domain.job_posting import StructuredJobPosting  # noqa: E402

__all__ = [
    "JobListingService",
    "JobMatchSummary",
    "JobMatchDetail",
    "DiscoveryEnqueueResult",
    "DiscoveryTriggerService",
    "JobRescrapeTriggerService",
    "StructuredJobPosting",
    "normalize_job_posting",
    "persist_structured_job",
    "structured_to_extracted",
    "load_resume_skills",
    "align_skills",
]
