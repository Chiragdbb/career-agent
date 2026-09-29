"""ATS compatibility advisory checks (deterministic + optional LLM summary)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

import fitz
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.models.schema import Job, ResumeVersion
from packages.domain.resume_models import StructuredResume
from packages.domain.skill_match import skills_match_fuzzy


class AtsIssue(BaseModel):
    code: str
    severity: str  # info | warning | error
    message: str


class AtsReport(BaseModel):
    score: int = Field(ge=0, le=100)
    issues: list[AtsIssue] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    summary: str | None = None


class AtsCompatibilityService:
    def check_ats_compatibility(
        self,
        *,
        resume_version: ResumeVersion,
        job: Job,
        canonical: StructuredResume,
        pdf_bytes: bytes,
        source_html: str,
    ) -> AtsReport:
        issues: list[AtsIssue] = []
        html_text = _strip_tags(source_html)
        pdf_text = _extract_pdf_text(pdf_bytes)
        overlap = _text_overlap_ratio(html_text, pdf_text)
        if overlap < 0.55:
            issues.append(
                AtsIssue(
                    code="text_extractability",
                    severity="error",
                    message=(
                        "PDF text differs significantly from HTML source — "
                        "ATS parsers may not read your content."
                    ),
                )
            )

        if re.search(r"display\s*:\s*flex|grid-template|multi-column", source_html, re.I):
            issues.append(
                AtsIssue(
                    code="multi_column_layout",
                    severity="warning",
                    message="Layout may use columns or grid — some ATS parsers struggle with this.",
                )
            )
        if "<table" in source_html.lower():
            issues.append(
                AtsIssue(
                    code="tables_in_body",
                    severity="warning",
                    message="Tables detected in resume body — prefer simple lists for ATS.",
                )
            )
        if re.search(r"[^\x00-\x7F]", html_text):
            issues.append(
                AtsIssue(
                    code="non_ascii_chars",
                    severity="info",
                    message="Non-ASCII characters present — verify rendering in target ATS.",
                )
            )

        job_skills = _job_skills(job)
        canonical_skills = list(canonical.skills or [])
        canonical_blob = _resume_text(canonical)
        missing_keywords: list[str] = []
        for skill in job_skills:
            if not any(skills_match_fuzzy(skill, cs) for cs in canonical_skills):
                continue
            if skill.lower() not in canonical_blob.lower():
                missing_keywords.append(skill)

        keyword_score = 100
        if job_skills:
            matched = sum(
                1
                for s in job_skills
                if any(skills_match_fuzzy(s, cs) for cs in canonical_skills)
            )
            keyword_score = int(round(100 * matched / len(job_skills)))

        penalty = sum(30 if i.severity == "error" else 10 if i.severity == "warning" else 2 for i in issues)
        score = max(0, min(100, keyword_score - min(penalty, 40)))

        return AtsReport(score=score, issues=issues, missing_keywords=missing_keywords[:20])

    def persist_report(
        self,
        session: Session,
        resume_version: ResumeVersion,
        report: AtsReport,
    ) -> None:
        resume_version.ats_score = report.score
        resume_version.ats_issues = [i.model_dump() for i in report.issues]
        resume_version.ats_checked_at = datetime.now(timezone.utc)
        session.flush()


def _job_skills(job: Job) -> list[str]:
    if job.skills:
        return [str(s) for s in job.skills if s]
    details = job.details if isinstance(job.details, dict) else {}
    raw = details.get("skills") or []
    return [str(s) for s in raw if isinstance(s, str)]


def _resume_text(resume: StructuredResume) -> str:
    parts: list[str] = []
    if resume.summary:
        parts.append(resume.summary)
    for exp in resume.experience:
        parts.extend(exp.bullets or [])
    parts.extend(resume.skills or [])
    return "\n".join(parts)


def _strip_tags(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return " ".join(page.get_text() for page in doc)
    finally:
        doc.close()


def _text_overlap_ratio(a: str, b: str) -> float:
    if not a.strip() or not b.strip():
        return 0.0
    ta = set(a.lower().split())
    tb = set(b.lower().split())
    if not ta:
        return 0.0
    return len(ta & tb) / len(ta)
