"""Validate tailored resume content against canonical facts — reject fabrications."""

from __future__ import annotations

import re
from dataclasses import dataclass

from packages.domain.resume_models import StructuredResume


@dataclass(frozen=True)
class FabricationIssue:
    field: str
    detail: str
    unsupported_value: str


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _canonical_tokens(resume: StructuredResume) -> set[str]:
    tokens: set[str] = set()
    for skill in resume.skills:
        tokens.add(_normalize(skill))
    if resume.summary:
        tokens.update(_words(resume.summary))
    for exp in resume.experience:
        for part in (exp.company, exp.title, exp.location, exp.start_date, exp.end_date):
            if part:
                tokens.add(_normalize(part))
                tokens.update(_words(part))
        for bullet in exp.bullets:
            tokens.update(_words(bullet))
            tokens.add(_normalize(bullet))
    for project in resume.projects:
        if project.name:
            tokens.add(_normalize(project.name))
            tokens.update(_words(project.name))
        if project.description:
            tokens.update(_words(project.description))
        for tech in project.technologies:
            tokens.add(_normalize(tech))
        for bullet in project.bullets:
            tokens.update(_words(bullet))
    for edu in resume.education:
        for part in (edu.institution, edu.degree, edu.field_of_study):
            if part:
                tokens.add(_normalize(part))
                tokens.update(_words(part))
    for cert in resume.certifications:
        if cert.name:
            tokens.add(_normalize(cert.name))
            tokens.update(_words(cert.name))
    return {t for t in tokens if t}


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9][a-z0-9+.#/-]{1,}", text.lower()) if len(w) > 1}


def _employers(resume: StructuredResume) -> set[str]:
    return {_normalize(e.company) for e in resume.experience if e.company}


def _titles(resume: StructuredResume) -> set[str]:
    return {_normalize(e.title) for e in resume.experience if e.title}


def _dates(resume: StructuredResume) -> set[str]:
    out: set[str] = set()
    for e in resume.experience:
        for d in (e.start_date, e.end_date):
            if d:
                out.add(_normalize(d))
    return out


def validate_against_canonical(
    canonical: StructuredResume,
    candidate: StructuredResume,
) -> list[FabricationIssue]:
    """Return fabrication issues for unsupported employers/titles/dates/projects/tech/metrics."""
    issues: list[FabricationIssue] = []
    canon_employers = _employers(canonical)
    canon_titles = _titles(canonical)
    canon_dates = _dates(canonical)
    canon_tokens = _canonical_tokens(canonical)
    canon_skills = {_normalize(s) for s in canonical.skills}
    canon_projects = {_normalize(p.name) for p in canonical.projects if p.name}
    canon_tech = set()
    for p in canonical.projects:
        canon_tech.update(_normalize(t) for t in p.technologies)

    for exp in candidate.experience:
        if exp.company and _normalize(exp.company) not in canon_employers:
            issues.append(
                FabricationIssue(
                    field="experience.company",
                    detail="Employer not present in canonical resume",
                    unsupported_value=exp.company,
                )
            )
        if exp.title and _normalize(exp.title) not in canon_titles:
            issues.append(
                FabricationIssue(
                    field="experience.title",
                    detail="Job title not present in canonical resume",
                    unsupported_value=exp.title,
                )
            )
        for d in (exp.start_date, exp.end_date):
            if d and _normalize(d) not in canon_dates:
                issues.append(
                    FabricationIssue(
                        field="experience.date",
                        detail="Date not present in canonical resume",
                        unsupported_value=d,
                    )
                )
        for bullet in exp.bullets:
            issues.extend(_metric_or_claim_issues("experience.bullet", bullet, canon_tokens))

    for project in candidate.projects:
        if project.name and _normalize(project.name) not in canon_projects:
            issues.append(
                FabricationIssue(
                    field="projects.name",
                    detail="Project not present in canonical resume",
                    unsupported_value=project.name,
                )
            )
        for tech in project.technologies:
            if _normalize(tech) not in canon_tech and _normalize(tech) not in canon_skills:
                issues.append(
                    FabricationIssue(
                        field="projects.technologies",
                        detail="Technology not present in canonical resume",
                        unsupported_value=tech,
                    )
                )

    for skill in candidate.skills:
        if _normalize(skill) not in canon_skills and _normalize(skill) not in canon_tokens:
            issues.append(
                FabricationIssue(
                    field="skills",
                    detail="Skill not present in canonical resume",
                    unsupported_value=skill,
                )
            )

    if candidate.summary:
        issues.extend(_metric_or_claim_issues("summary", candidate.summary, canon_tokens))

    return issues


_METRIC_RE = re.compile(
    r"(\d+\s*%|\d+\s*x\b|\$\s*\d[\d,.]*(?:\s*[kmb])?|\b\d{2,}\+?\s*(?:users|customers|engineers|people)\b)",
    re.IGNORECASE,
)


def _metric_or_claim_issues(
    field: str,
    text: str,
    canon_tokens: set[str],
) -> list[FabricationIssue]:
    issues: list[FabricationIssue] = []
    for match in _METRIC_RE.finditer(text):
        metric = match.group(0)
        # Allow metrics only if the exact metric string appears in canonical text tokens/phrases.
        if _normalize(metric) not in canon_tokens and metric.lower() not in " ".join(canon_tokens):
            # Also allow if full metric substring exists in any canonical token phrase.
            if not any(metric.lower() in token for token in canon_tokens):
                issues.append(
                    FabricationIssue(
                        field=field,
                        detail="Metric/number not supported by canonical facts",
                        unsupported_value=metric,
                    )
                )
    return issues
