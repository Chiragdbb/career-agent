"""Normalize and persist structured job postings from the tiered scrape pipeline."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models.enums import CompanyStatus, JobMatchStatus, JobStatus
from database.models.schema import Company, CompanyDomain, Job, JobMatch
from packages.domain.exceptions import DomainError
from packages.domain.job_models import ExtractedJob
from packages.domain.job_posting import StructuredJobPosting


def normalize_job_posting(raw: dict[str, Any] | StructuredJobPosting) -> StructuredJobPosting:
    """Validate scrape output against the fixed schema before persistence."""
    if isinstance(raw, StructuredJobPosting):
        return raw
    return StructuredJobPosting.model_validate(raw)


def structured_to_extracted(posting: StructuredJobPosting) -> ExtractedJob:
    """Bridge to the existing ExtractedJob shape used by discovery/matching."""
    remote = posting.remote_type
    work_arrangement = None
    if remote == "onsite":
        work_arrangement = "on_site"
    elif remote in ("remote", "hybrid"):
        work_arrangement = remote

    return ExtractedJob(
        title=posting.title,
        company_name=posting.company_name,
        location=posting.location or None,
        work_arrangement=work_arrangement,
        employment_type=posting.employment_type,
        seniority=posting.seniority,
        salary_min=int(posting.salary_min) if posting.salary_min is not None else None,
        salary_max=int(posting.salary_max) if posting.salary_max is not None else None,
        currency=posting.salary_currency,
        description=_compose_description(posting),
        skills=list(posting.skills),
        url=posting.application_url,
        external_id=posting.external_job_id,
        posted_at=posting.posted_at.isoformat() if posting.posted_at else None,
    )


def _compose_description(posting: StructuredJobPosting) -> str:
    parts = [posting.description.strip()]
    if posting.requirements:
        parts.append("Requirements:\n- " + "\n- ".join(posting.requirements))
    return "\n\n".join(p for p in parts if p)


def persist_structured_job(
    session: Session,
    posting: StructuredJobPosting,
    *,
    user_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
) -> Job:
    """Dedup on (external_job_id, company_domain) then insert/update jobs row."""
    validated = normalize_job_posting(posting)
    company = _get_or_create_company(session, validated.company_name, validated.company_domain)
    domain = validated.company_domain or _domain_from_url(validated.application_url)
    scraped_at = validated.scraped_at
    if scraped_at.tzinfo is None:
        scraped_at = scraped_at.replace(tzinfo=timezone.utc)

    existing = (
        session.query(Job)
        .filter(
            Job.external_id == validated.external_job_id,
            Job.company_domain == domain,
        )
        .one_or_none()
    )
    if existing is None and validated.application_url:
        existing = (
            session.query(Job)
            .filter(Job.url == validated.application_url.strip())
            .one_or_none()
        )

    details = validated.to_llm_payload()
    if existing is not None:
        _apply_posting_fields(existing, validated, company_id=company.id, domain=domain, details=details, scraped_at=scraped_at, run_id=run_id)
        session.flush()
        if user_id is not None:
            _ensure_match(session, user_id, existing.id)
        return existing

    job = Job(
        id=uuid.uuid4(),
        company_id=company.id,
        status=JobStatus.active,
        title=validated.title,
        url=validated.application_url,
        external_id=validated.external_job_id,
        source=validated.source,
        company_domain=domain,
        description=_compose_description(validated),
        details=details,
        skills=list(validated.skills) or None,
        remote_type=validated.remote_type,
        employment_type=validated.employment_type,
        seniority=validated.seniority,
        salary_min=validated.salary_min,
        salary_max=validated.salary_max,
        salary_currency=validated.salary_currency,
        posted_at=_posted_at_datetime(validated),
        last_scraped_at=scraped_at,
        scraped_at=scraped_at,
        discovery_run_id=run_id,
    )
    try:
        with session.begin_nested():
            session.add(job)
            session.flush()
    except IntegrityError as exc:
        existing = (
            session.query(Job)
            .filter(
                Job.external_id == validated.external_job_id,
                Job.company_domain == domain,
            )
            .one_or_none()
        )
        if existing is None:
            raise DomainError("Failed to persist job due to conflict") from exc
        if user_id is not None:
            _ensure_match(session, user_id, existing.id)
        return existing

    if user_id is not None:
        _ensure_match(session, user_id, job.id)
    return job


def _apply_posting_fields(
    job: Job,
    validated: StructuredJobPosting,
    *,
    company_id: uuid.UUID,
    domain: str | None,
    details: dict[str, Any],
    scraped_at: datetime,
    run_id: uuid.UUID | None,
) -> None:
    job.title = validated.title
    job.url = validated.application_url
    job.external_id = validated.external_job_id
    job.source = validated.source
    job.company_domain = domain
    job.company_id = company_id
    job.description = _compose_description(validated)
    job.details = details
    job.skills = list(validated.skills) or None
    job.remote_type = validated.remote_type
    job.employment_type = validated.employment_type
    job.seniority = validated.seniority
    job.salary_min = validated.salary_min
    job.salary_max = validated.salary_max
    job.salary_currency = validated.salary_currency
    job.posted_at = _posted_at_datetime(validated) or job.posted_at
    job.last_scraped_at = scraped_at
    job.scraped_at = scraped_at
    if run_id is not None:
        job.discovery_run_id = run_id


def _posted_at_datetime(validated: StructuredJobPosting) -> datetime | None:
    if validated.posted_at is None:
        return None
    return datetime(
        validated.posted_at.year,
        validated.posted_at.month,
        validated.posted_at.day,
        tzinfo=timezone.utc,
    )


def _domain_from_url(url: str) -> str | None:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    return host or None


def _get_or_create_company(
    session: Session,
    name: str,
    domain: str | None,
) -> Company:
    cleaned = (name or "").strip() or "Unknown Company"
    if domain:
        linked = (
            session.query(Company)
            .join(CompanyDomain, CompanyDomain.company_id == Company.id)
            .filter(CompanyDomain.domain == domain)
            .first()
        )
        if linked is not None:
            return linked
    existing = (
        session.query(Company)
        .filter(Company.name == cleaned)
        .order_by(Company.created_at.asc())
        .first()
    )
    if existing is not None:
        if domain:
            _ensure_company_domain(session, existing.id, domain)
        return existing
    company = Company(id=uuid.uuid4(), name=cleaned, status=CompanyStatus.active)
    if domain:
        company.url = f"https://{domain}"
    session.add(company)
    session.flush()
    if domain:
        _ensure_company_domain(session, company.id, domain)
    return company


def _ensure_company_domain(session: Session, company_id: uuid.UUID, domain: str) -> None:
    from database.models.enums import CompanyDomainStatus

    row = (
        session.query(CompanyDomain)
        .filter(CompanyDomain.company_id == company_id, CompanyDomain.domain == domain)
        .one_or_none()
    )
    if row is None:
        session.add(
            CompanyDomain(
                id=uuid.uuid4(),
                company_id=company_id,
                domain=domain,
                status=CompanyDomainStatus.unverified,
            )
        )
        session.flush()


def _ensure_match(session: Session, user_id: uuid.UUID, job_id: uuid.UUID) -> JobMatch:
    row = (
        session.query(JobMatch)
        .filter(JobMatch.user_id == user_id, JobMatch.job_id == job_id)
        .one_or_none()
    )
    if row is not None:
        return row
    row = JobMatch(
        id=uuid.uuid4(),
        user_id=user_id,
        job_id=job_id,
        status=JobMatchStatus.new,
    )
    session.add(row)
    session.flush()
    return row
