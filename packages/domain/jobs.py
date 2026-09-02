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
from packages.domain.job_match import JobMatchService, ScoreBreakdown
from packages.domain.preferences import PreferencesService
from packages.domain.resume_models import StructuredResume
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
        alignment = _skill_alignment_from_match(match)
        if alignment is None:
            matched, missing = align_skills(job_skills, resume_skills)
            possible: list[str] = []
        else:
            matched = alignment.get("matched", [])
            possible = alignment.get("possible", [])
            missing = alignment.get("missing", [])
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
        return JobMatchDetail(
            id=match.id,
            job_id=match.job_id,
            status=match.status.value if hasattr(match.status, "value") else str(match.status),
            score=match.score if match.score is not None else (breakdown.total if breakdown else None),
            title=job.title,
            company_name=company.name if company else None,
            location=_as_str(details.get("location")),
            work_arrangement=_as_str(details.get("work_arrangement")),
            url=job.url,
            description=job.description,
            job_skills=job_skills,
            matched_skills=matched_skills,
            possible_matches=possible_matches,
            missing_skills=missing_skills,
            score_breakdown=breakdown,
            explanation=match.fit_summary,
            created_at=match.created_at,
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
        run.status = WorkflowRunStatus.cancelling
        metadata = dict(run.metadata_json or {})
        metadata["current_step"] = "cancelling"
        metadata["status_message"] = "Cancellation requested"
        metadata["cancel_requested_at"] = datetime.now(timezone.utc).isoformat()
        run.metadata_json = metadata
        run.error = None
        self._session.commit()
        if cancellation is not None:
            cancellation.request_cancel(run_id)
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


def load_resume_skills(session: Session, user_id: uuid.UUID) -> list[str]:
    """Load skills from the user's most recent finalized resume version."""
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
    if version is None or not isinstance(version.sections, dict):
        return []
    try:
        structured = StructuredResume.model_validate(version.sections)
    except Exception:
        return []
    return [skill.strip() for skill in structured.skills if skill.strip()]


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
    resume_lower = {skill.lower(): skill for skill in resume_skills}
    matched: list[str] = []
    missing: list[str] = []
    for skill in job_skills:
        if skill.lower() in resume_lower:
            matched.append(skill)
        else:
            missing.append(skill)
    return matched, missing


def _job_skills(job: Job) -> list[str]:
    details = job.details if isinstance(job.details, dict) else {}
    raw = details.get("skills") or []
    return [str(skill).strip() for skill in raw if isinstance(skill, str) and str(skill).strip()]


def _as_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
