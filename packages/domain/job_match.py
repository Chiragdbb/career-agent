"""Job matching against user preferences with tiered skill + semantic hybrid scoring.

Deterministic preference scoring remains primary. Semantic similarity (pgvector
embeddings) augments the total when embeddings are available — it never replaces
role/location/salary/skills/seniority scoring.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from database.models.enums import JobMatchStatus
from database.models.schema import Company, Job, JobMatch, ResumeVersion, UserProfile
from packages.domain.embeddings import EmbeddingService
from packages.domain.exceptions import NotFoundError
from packages.domain.preferences import (
    PreferenceSettings,
    PreferencesService,
    WorkArrangement,
)
from packages.domain.skill_match import SkillMatchService
from packages.providers.embedding import EmbeddingProvider

# Versioned hybrid algorithm: deterministic core + optional semantic blend.
SCORING_ALGORITHM_VERSION = "v2.0-hybrid-semantic"
SEMANTIC_BLEND_WEIGHT = 0.15

_NOTE_LABELS: dict[str, str] = {
    "missing_skills": "Job listing had no skills listed",
    "no_resume_skills": "No skills found on your resume",
    "semantic_disabled": "Semantic matching unavailable",
    "missing_job_embedding": "Job embedding not ready yet",
    "missing_candidate_embedding": "Resume embedding not ready yet",
    "missing_location": "Job location not specified",
    "missing_company": "Company name not specified",
    "salary_currency_mismatch": "Salary currency does not match your preference",
    "currency_mismatch": "Salary currency does not match your preference",
    "missing_salary": "Job salary not specified",
}


def format_score_pct(value: float) -> str:
    return f"{int(round(max(0.0, min(1.0, value)) * 100))}%"


def format_note(note: str) -> str:
    return _NOTE_LABELS.get(note, note.replace("_", " ").capitalize())


def format_fit_summary(breakdown: ScoreBreakdown) -> str:
    """Human-readable match explanation with percentages (not raw 0–1 floats)."""
    lines = [
        f"Match score: {format_score_pct(breakdown.total)}",
        (
            f"Role {format_score_pct(breakdown.role)} · "
            f"Location {format_score_pct(breakdown.location)} · "
            f"Work style {format_score_pct(breakdown.work_arrangement)} · "
            f"Salary {format_score_pct(breakdown.salary)} · "
            f"Skills {format_score_pct(breakdown.skills)} · "
            f"Seniority {format_score_pct(breakdown.seniority)}"
        ),
    ]
    if breakdown.notes:
        lines.append("Notes: " + "; ".join(format_note(n) for n in breakdown.notes))
    return "\n".join(lines)


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
    semantic: float = 0.5
    deterministic_total: float = 0.0
    algorithm_version: str = SCORING_ALGORITHM_VERSION
    notes: tuple[str, ...] = ()


class JobMatchService:
    """Score and persist JobMatch rows for one tenant."""

    def __init__(
        self,
        session: Session,
        user_id: uuid.UUID,
        *,
        weights: MatchWeights | None = None,
        embedding: EmbeddingProvider | None = None,
        skill_high_threshold: float = 0.85,
        skill_low_threshold: float = 0.7,
        skill_possible_weight: float = 0.5,
        semantic_blend_weight: float = SEMANTIC_BLEND_WEIGHT,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._weights = weights or MatchWeights()
        self._embedding = embedding
        self._skill_matcher = SkillMatchService(
            embedding,
            high_threshold=skill_high_threshold,
            low_threshold=skill_low_threshold,
        )
        self._skill_possible_weight = skill_possible_weight
        self._semantic_blend = max(0.0, min(0.5, semantic_blend_weight))

    def score_job(
        self,
        job: Job,
        preferences: PreferenceSettings,
        *,
        company_name: str | None = None,
        resume_skills: list[str] | None = None,
        profile: UserProfile | None = None,
        resume_version: ResumeVersion | None = None,
    ) -> ScoreBreakdown:
        details = job.details if isinstance(job.details, dict) else {}
        title = (job.title or "").lower()
        location = str(details.get("location") or "").lower()
        work = str(details.get("work_arrangement") or "").lower()
        seniority = str(details.get("seniority") or "").lower()
        job_skills = [
            str(s).strip()
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
        skill_alignment = self._skill_matcher.align(job_skills, resume_skills or [])
        skills_score = self._skill_matcher.skills_score(
            skill_alignment,
            possible_weight=self._skill_possible_weight,
        )
        if not job_skills:
            notes.append("missing_skills")
        if not resume_skills:
            notes.append("no_resume_skills")
        seniority_score = _seniority_score(seniority, preferences.seniority)

        if not location and not work:
            notes.append("missing_location")
        if company_name is None and not details.get("company_name"):
            notes.append("missing_company")

        w = self._weights
        deterministic = (
            role_score * w.role
            + location_score * w.location
            + arrangement_score * w.work_arrangement
            + salary_score * w.salary
            + skills_score * w.skills
            + seniority_score * w.seniority
        )

        semantic = 0.5
        if self._embedding is not None:
            embed_svc = EmbeddingService(self._session, self._embedding)
            semantic = embed_svc.similarity_against_profile(
                job, profile, resume_version=resume_version
            )
            if job.embedding is None:
                notes.append("missing_job_embedding")
            elif profile is None or profile.embedding is None:
                if resume_version is None or resume_version.embedding is None:
                    notes.append("missing_candidate_embedding")
        else:
            notes.append("semantic_disabled")

        blend = self._semantic_blend
        total = deterministic * (1.0 - blend) + semantic * blend
        return ScoreBreakdown(
            total=round(total, 4),
            role=role_score,
            location=location_score,
            work_arrangement=arrangement_score,
            salary=salary_score,
            skills=skills_score,
            seniority=seniority_score,
            semantic=round(semantic, 4),
            deterministic_total=round(deterministic, 4),
            algorithm_version=SCORING_ALGORITHM_VERSION,
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
        profile = (
            self._session.query(UserProfile)
            .filter(UserProfile.user_id == self._user_id)
            .one_or_none()
        )
        resume_version = (
            self._session.query(ResumeVersion)
            .filter(ResumeVersion.user_id == self._user_id)
            .order_by(ResumeVersion.created_at.desc())
            .first()
        )
        breakdown = self.score_job(
            job,
            prefs,
            company_name=company.name if company else None,
            resume_skills=resume_skills,
            profile=profile,
            resume_version=resume_version,
        )
        details = job.details if isinstance(job.details, dict) else {}
        job_skills = [
            str(s).strip()
            for s in (details.get("skills") or [])
            if isinstance(s, str) and s.strip()
        ]
        skill_alignment = self._skill_matcher.align(job_skills, resume_skills or [])
        alignment_payload = {
            "matched": skill_alignment.matched,
            "possible": skill_alignment.possible,
            "missing": skill_alignment.missing,
            "scoring": {
                "version": breakdown.algorithm_version,
                "deterministic": breakdown.deterministic_total,
                "semantic": breakdown.semantic,
                "blend_weight": self._semantic_blend,
            },
        }

        row = (
            self._session.query(JobMatch)
            .filter(JobMatch.user_id == self._user_id, JobMatch.job_id == job_id)
            .one_or_none()
        )
        summary = format_fit_summary(breakdown)

        if row is None:
            row = JobMatch(
                id=uuid.uuid4(),
                user_id=self._user_id,
                job_id=job_id,
                status=JobMatchStatus.new,
                score=breakdown.total,
                fit_summary=summary,
                skill_alignment=alignment_payload,
                scoring_algorithm_version=breakdown.algorithm_version,
                semantic_score=breakdown.semantic,
            )
            self._session.add(row)
        else:
            row.score = breakdown.total
            row.fit_summary = summary
            row.skill_alignment = alignment_payload
            row.scoring_algorithm_version = breakdown.algorithm_version
            row.semantic_score = breakdown.semantic
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
    if salary_ceiling >= int(minimum_salary * 0.85):
        return 0.4
    return 0.0


def _seniority_score(seniority: str, preferred: list) -> float:
    if not preferred:
        return 0.5
    if not seniority:
        return 0.3
    values = {item.value if hasattr(item, "value") else str(item) for item in preferred}
    return 1.0 if seniority in values else 0.0
