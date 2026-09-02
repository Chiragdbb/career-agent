"""Deterministic job matching against user preferences (no embeddings)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from database.models.enums import JobMatchStatus
from database.models.schema import Company, Job, JobMatch
from packages.domain.exceptions import NotFoundError
from packages.domain.preferences import (
    PreferenceSettings,
    PreferencesService,
    WorkArrangement,
)


@dataclass(frozen=True)
class MatchWeights:
    role: float = 0.30
    location: float = 0.15
    work_arrangement: float = 0.15
    salary: float = 0.20
    skills: float = 0.15
    seniority: float = 0.05


@dataclass(frozen=True)
class ScoreBreakdown:
    total: float
    role: float
    location: float
    work_arrangement: float
    salary: float
    skills: float
    seniority: float
    notes: tuple[str, ...] = ()


class JobMatchService:
    """Score and persist JobMatch rows for one tenant."""

    def __init__(
        self,
        session: Session,
        user_id: uuid.UUID,
        *,
        weights: MatchWeights | None = None,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._weights = weights or MatchWeights()

    def score_job(
        self,
        job: Job,
        preferences: PreferenceSettings,
        *,
        company_name: str | None = None,
        resume_skills: list[str] | None = None,
    ) -> ScoreBreakdown:
        details = job.details if isinstance(job.details, dict) else {}
        title = (job.title or "").lower()
        location = str(details.get("location") or "").lower()
        work = str(details.get("work_arrangement") or "").lower()
        seniority = str(details.get("seniority") or "").lower()
        job_skills = [
            str(s).lower()
            for s in (details.get("skills") or [])
            if isinstance(s, str) and s.strip()
        ]
        salary_max = details.get("salary_max")
        salary_min = details.get("salary_min")
        try:
            salary_ceiling = int(salary_max) if salary_max is not None else (
                int(salary_min) if salary_min is not None else None
            )
        except (TypeError, ValueError):
            salary_ceiling = None

        notes: list[str] = []

        role_score = _role_score(title, preferences.target_roles)
        location_score = _location_score(location, work, preferences.locations)
        arrangement_score = _arrangement_score(work, preferences.work_arrangements)
        job_currency = details.get("currency")
        salary_score = _salary_score(
            salary_ceiling,
            preferences.minimum_salary,
            str(job_currency) if job_currency is not None else None,
            preferences.salary_currency,
            notes,
        )
        skills_score = _skills_score(job_skills, resume_skills or [], notes)
        seniority_score = _seniority_score(seniority, preferences.seniority)

        if not location and not work:
            notes.append("missing_location")
        if company_name is None and not details.get("company_name"):
            notes.append("missing_company")

        w = self._weights
        total = (
            role_score * w.role
            + location_score * w.location
            + arrangement_score * w.work_arrangement
            + salary_score * w.salary
            + skills_score * w.skills
            + seniority_score * w.seniority
        )
        return ScoreBreakdown(
            total=round(total, 4),
            role=role_score,
            location=location_score,
            work_arrangement=arrangement_score,
            salary=salary_score,
            skills=skills_score,
            seniority=seniority_score,
            notes=tuple(notes),
        )

    def upsert_match(
        self,
        job_id: uuid.UUID,
        *,
        preferences: PreferenceSettings | None = None,
        resume_skills: list[str] | None = None,
    ) -> JobMatch:
        job = self._session.query(Job).filter(Job.id == job_id).one_or_none()
        if job is None:
            raise NotFoundError("Job not found")
        company = self._session.query(Company).filter(Company.id == job.company_id).one_or_none()
        prefs = preferences or PreferencesService(self._session, self._user_id).get_settings()
        breakdown = self.score_job(
            job,
            prefs,
            company_name=company.name if company else None,
            resume_skills=resume_skills,
        )

        row = (
            self._session.query(JobMatch)
            .filter(JobMatch.user_id == self._user_id, JobMatch.job_id == job_id)
            .one_or_none()
        )
        summary = (
            f"score={breakdown.total}; "
            f"role={breakdown.role}; location={breakdown.location}; "
            f"salary={breakdown.salary}; skills={breakdown.skills}"
        )
        if breakdown.notes:
            summary += f"; notes={','.join(breakdown.notes)}"

        if row is None:
            row = JobMatch(
                id=uuid.uuid4(),
                user_id=self._user_id,
                job_id=job_id,
                status=JobMatchStatus.new,
                score=breakdown.total,
                fit_summary=summary,
            )
            self._session.add(row)
        else:
            row.score = breakdown.total
            row.fit_summary = summary
        self._session.commit()
        self._session.refresh(row)
        return row


def _role_score(title: str, target_roles: list[str]) -> float:
    if not target_roles:
        return 0.5
    for role in target_roles:
        tokens = [t for t in role.lower().split() if t]
        if tokens and all(token in title for token in tokens):
            return 1.0
        if any(token in title for token in tokens):
            return 0.6
    return 0.0


def _location_score(location: str, work: str, preferred: list[str]) -> float:
    if not preferred:
        return 0.5
    haystack = f"{location} {work}".strip()
    if not haystack:
        return 0.0
    for pref in preferred:
        p = pref.lower()
        if p in haystack:
            return 1.0
        if p == "remote" and "remote" in haystack:
            return 1.0
    return 0.0


def _arrangement_score(work: str, preferred: list[WorkArrangement]) -> float:
    if not preferred:
        return 0.5
    if not work:
        return 0.0
    preferred_values = {item.value for item in preferred}
    if work in preferred_values:
        return 1.0
    if "remote" in preferred_values and work == "remote":
        return 1.0
    return 0.0


def _salary_score(
    salary_ceiling: int | None,
    minimum_salary: int | None,
    job_currency: str | None,
    user_currency: str | None,
    notes: list[str],
) -> float:
    if minimum_salary is None:
        return 0.5
    if salary_ceiling is None:
        notes.append("missing_salary")
        return 0.0
    user_cur = (user_currency or "USD").upper()
    job_cur = (job_currency or "").strip().upper()
    if job_cur and job_cur != user_cur:
        notes.append("currency_mismatch")
        return 0.5
    if salary_ceiling >= minimum_salary:
        return 1.0
    # Partial credit if within 15%.
    if salary_ceiling >= int(minimum_salary * 0.85):
        return 0.4
    return 0.0


def _skills_score(
    job_skills: list[str], resume_skills: list[str], notes: list[str]
) -> float:
    if not job_skills:
        notes.append("missing_skills")
        return 0.5
    if not resume_skills:
        return 0.3
    resume_set = {s.lower() for s in resume_skills}
    hits = sum(1 for skill in job_skills if skill in resume_set)
    return hits / max(len(job_skills), 1)


def _seniority_score(seniority: str, preferred: list) -> float:
    if not preferred:
        return 0.5
    if not seniority:
        return 0.3
    values = {item.value if hasattr(item, "value") else str(item) for item in preferred}
    return 1.0 if seniority in values else 0.0
