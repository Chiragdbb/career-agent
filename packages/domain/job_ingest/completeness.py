"""Score job record completeness (0–100) for UI badges and workflow gates."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from database.models.schema import Job
from packages.domain.job_posting import StructuredJobPosting

DEFAULT_COMPLETENESS_THRESHOLD = 55


def completeness_threshold() -> int:
    raw = (os.getenv("JOB_COMPLETENESS_THRESHOLD") or str(DEFAULT_COMPLETENESS_THRESHOLD)).strip()
    try:
        return max(0, min(100, int(raw)))
    except ValueError:
        return DEFAULT_COMPLETENESS_THRESHOLD


@dataclass(frozen=True)
class JobCompletenessResult:
    score: int
    missing_fields: list[str]


class JobCompletenessService:
    """Deterministic completeness scoring — no LLM."""

    _WEIGHTS: dict[str, int] = {
        "title": 10,
        "company": 10,
        "location": 8,
        "remote_type": 7,
        "seniority": 5,
        "salary": 12,
        "skills": 15,
        "description": 18,
        "posted_at": 7,
        "source_url": 8,
    }

    def score_job(self, job: Job) -> JobCompletenessResult:
        missing: list[str] = []
        earned = 0
        total = sum(self._WEIGHTS.values())

        checks: list[tuple[str, bool]] = [
            ("title", bool((job.title or "").strip())),
            ("company", job.company_id is not None),
            ("location", bool(self._location(job))),
            ("remote_type", bool(job.remote_type)),
            ("seniority", bool(job.seniority)),
            ("salary", job.salary_min is not None or job.salary_max is not None),
            ("skills", bool(job.skills and len(job.skills) >= 2)),
            ("description", len((job.description or "").strip()) >= 120),
            ("posted_at", job.posted_at is not None),
            ("source_url", bool((job.url or "").strip())),
        ]
        for field, ok in checks:
            weight = self._WEIGHTS[field]
            if ok:
                earned += weight
            else:
                missing.append(field)

        score = int(round(100 * earned / total)) if total else 0
        return JobCompletenessResult(score=score, missing_fields=missing)

    def score_posting(self, posting: StructuredJobPosting) -> JobCompletenessResult:
        """Score in-memory posting before persist."""
        missing: list[str] = []
        earned = 0
        total = sum(self._WEIGHTS.values())

        checks: list[tuple[str, bool]] = [
            ("title", bool(posting.title.strip())),
            ("company", bool(posting.company_name.strip())),
            ("location", bool((posting.location or "").strip())),
            ("remote_type", posting.remote_type is not None),
            ("seniority", bool(posting.seniority)),
            ("salary", posting.salary_min is not None or posting.salary_max is not None),
            ("skills", len(posting.skills) >= 2),
            ("description", len(posting.description.strip()) >= 120),
            ("posted_at", posting.posted_at is not None),
            ("source_url", bool(posting.application_url.strip())),
        ]
        for field, ok in checks:
            weight = self._WEIGHTS[field]
            if ok:
                earned += weight
            else:
                missing.append(field)
        score = int(round(100 * earned / total)) if total else 0
        return JobCompletenessResult(score=score, missing_fields=missing)

    def apply_to_job(
        self,
        job: Job,
        *,
        provenance: str | None = None,
        posting: StructuredJobPosting | None = None,
    ) -> JobCompletenessResult:
        result = self.score_posting(posting) if posting is not None else self.score_job(job)
        job.completeness_score = result.score
        job.missing_fields = result.missing_fields
        if provenance:
            job.extraction_provenance = provenance
        return result

    @staticmethod
    def _location(job: Job) -> str:
        details = job.details if isinstance(job.details, dict) else {}
        loc = details.get("location")
        if isinstance(loc, str) and loc.strip():
            return loc.strip()
        return ""


def job_meets_workflow_threshold(job: Job, *, override: bool = False) -> tuple[bool, dict[str, Any]]:
    if override:
        return True, {"overridden": True}
    threshold = completeness_threshold()
    score = job.completeness_score
    if score is None:
        score = JobCompletenessService().score_job(job).score
    ok = score >= threshold
    return ok, {
        "completeness_score": score,
        "threshold": threshold,
        "missing_fields": job.missing_fields or [],
    }
