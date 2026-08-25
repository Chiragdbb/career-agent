"""ResumeCustomizationService — tailor resume without inventing facts."""

from __future__ import annotations

import copy
import hashlib
import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from database.models.enums import ResumeVersionStatus
from database.models.schema import Job, JobMatch, Resume, ResumeVersion
from packages.domain.exceptions import DomainError, NotFoundError
from packages.domain.resume_models import PARSER_VERSION, StructuredResume
from packages.domain.resume_validation import FabricationIssue, validate_against_canonical


class ResumeCustomizationService:
    """Canonical structured resume + job + match → validated ResumeVersion."""

    def __init__(self, session: Session, user_id: uuid.UUID) -> None:
        self._session = session
        self._user_id = user_id

    def customize_for_match(
        self,
        *,
        resume_id: uuid.UUID,
        job_match_id: uuid.UUID,
        emphasis_skills: list[str] | None = None,
        summary_override: str | None = None,
        max_bullets_per_role: int = 4,
    ) -> ResumeVersion:
        resume = (
            self._session.query(Resume)
            .filter(Resume.id == resume_id, Resume.user_id == self._user_id)
            .one_or_none()
        )
        if resume is None:
            raise NotFoundError("Resume not found")

        match = (
            self._session.query(JobMatch)
            .filter(JobMatch.id == job_match_id, JobMatch.user_id == self._user_id)
            .one_or_none()
        )
        if match is None:
            raise NotFoundError("Job match not found")

        job = self._session.query(Job).filter(Job.id == match.job_id).one_or_none()
        if job is None:
            raise NotFoundError("Job not found")

        canonical_version = (
            self._session.query(ResumeVersion)
            .filter(
                ResumeVersion.resume_id == resume_id,
                ResumeVersion.user_id == self._user_id,
            )
            .order_by(ResumeVersion.created_at.desc())
            .first()
        )
        if canonical_version is None or not canonical_version.sections:
            raise DomainError("Canonical structured resume required before customization")

        canonical = StructuredResume.model_validate(canonical_version.sections)
        tailored = self.customize_structured(
            canonical,
            job=job,
            match_score=match.score,
            emphasis_skills=emphasis_skills,
            summary_override=summary_override,
            max_bullets_per_role=max_bullets_per_role,
        )

        issues = validate_against_canonical(canonical, tailored)
        if issues:
            raise DomainError(_format_issues(issues))

        # Mark prior drafts for this resume as superseded when creating a new tailored draft.
        for prior in (
            self._session.query(ResumeVersion)
            .filter(
                ResumeVersion.resume_id == resume_id,
                ResumeVersion.user_id == self._user_id,
                ResumeVersion.status == ResumeVersionStatus.draft,
            )
            .all()
        ):
            prior.status = ResumeVersionStatus.superseded

        payload = tailored.model_dump()
        content_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()
        version = ResumeVersion(
            id=uuid.uuid4(),
            resume_id=resume_id,
            user_id=self._user_id,
            status=ResumeVersionStatus.draft,
            content_hash=content_hash,
            plain_text=_to_plain_text(tailored),
            sections=payload,
            parser_version=f"{PARSER_VERSION}+custom-v1",
        )
        self._session.add(version)
        self._session.commit()
        self._session.refresh(version)
        return version

    def customize_structured(
        self,
        canonical: StructuredResume,
        *,
        job: Job | None = None,
        match_score: float | None = None,
        emphasis_skills: list[str] | None = None,
        summary_override: str | None = None,
        max_bullets_per_role: int = 4,
    ) -> StructuredResume:
        """Allowed: rewrite/reorder/emphasize/shorten/adjust summary. Forbidden: invent facts."""
        tailored = StructuredResume.model_validate(copy.deepcopy(canonical.model_dump()))
        job_skills = _job_skills(job)
        emphasis = [
            s for s in (emphasis_skills or []) if _norm(s) in {_norm(x) for x in canonical.skills}
        ]

        # Reorder skills: job-overlapping and emphasis first; never add unknown skills.
        if tailored.skills:
            overlap = [s for s in tailored.skills if _norm(s) in {_norm(j) for j in job_skills}]
            rest = [s for s in tailored.skills if s not in overlap]
            emphasized = [s for s in rest if _norm(s) in {_norm(e) for e in emphasis}]
            remaining = [s for s in rest if s not in emphasized]
            tailored.skills = overlap + emphasized + remaining

        # Reorder experience by keyword overlap with job title/description; shorten bullets.
        job_text = _job_text(job)
        tailored.experience = sorted(
            tailored.experience,
            key=lambda e: -_overlap_score(e.title or "", e.bullets, job_text),
        )
        for exp in tailored.experience:
            ranked = sorted(
                exp.bullets,
                key=lambda b: -_overlap_score("", [b], job_text),
            )
            exp.bullets = ranked[:max(1, max_bullets_per_role)] if ranked else []

        if summary_override is not None:
            tailored.summary = summary_override.strip() or tailored.summary
        elif tailored.summary and job_text:
            # Light emphasis: keep original summary (no invention). Caller may LLM-rewrite later
            # but validation still applies.
            tailored.summary = tailored.summary.strip()

        # Attach customization metadata without inventing candidate facts.
        _ = match_score  # reserved for future ranking hints
        return tailored

    def validate_or_raise(
        self,
        canonical: StructuredResume,
        candidate: StructuredResume,
    ) -> None:
        issues = validate_against_canonical(canonical, candidate)
        if issues:
            raise DomainError(_format_issues(issues))


def _job_skills(job: Job | None) -> list[str]:
    if job is None:
        return []
    details: dict[str, Any] = job.details if isinstance(job.details, dict) else {}
    skills = details.get("skills") or []
    return [str(s) for s in skills if isinstance(s, str)]


def _job_text(job: Job | None) -> str:
    if job is None:
        return ""
    details: dict[str, Any] = job.details if isinstance(job.details, dict) else {}
    parts = [
        job.title or "",
        job.description or "",
        " ".join(_job_skills(job)),
        str(details.get("seniority") or ""),
    ]
    return " ".join(parts).lower()


def _overlap_score(title: str, bullets: list[str], job_text: str) -> int:
    if not job_text:
        return 0
    blob = f"{title} " + " ".join(bullets)
    words = {w for w in re_split(blob) if len(w) > 2}
    job_words = set(re_split(job_text))
    return len(words & job_words)


def re_split(text: str) -> list[str]:
    import re

    return re.findall(r"[a-z0-9][a-z0-9+.#/-]{1,}", text.lower())


def _norm(value: str) -> str:
    return value.strip().lower()


def _to_plain_text(resume: StructuredResume) -> str:
    lines: list[str] = []
    if resume.contact.full_name:
        lines.append(resume.contact.full_name)
    if resume.summary:
        lines.append(resume.summary)
    if resume.skills:
        lines.append("Skills: " + ", ".join(resume.skills))
    for exp in resume.experience:
        header = " | ".join(p for p in (exp.title, exp.company, exp.start_date, exp.end_date) if p)
        lines.append(header)
        lines.extend(f"- {b}" for b in exp.bullets)
    return "\n".join(lines)


def _format_issues(issues: list[FabricationIssue]) -> str:
    parts = [f"{i.field}: {i.detail} ({i.unsupported_value})" for i in issues]
    return "Unsupported resume additions rejected: " + "; ".join(parts)
