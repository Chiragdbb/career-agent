"""Resolve and score company domain before contact enrichment tiers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from database.models.enums import CompanyDomainStatus
from database.models.schema import Company, CompanyDomain, Job


class DomainConfidence(StrEnum):
    exact_from_posting = "exact_from_posting"
    guessed_and_verified = "guessed_and_verified"
    unverified = "unverified"


@dataclass(frozen=True)
class ResolvedCompanyDomain:
    domain: str | None
    confidence: DomainConfidence
    source: str


_EMAIL_DOMAIN_RE = re.compile(r"@[\w.-]+\.(\w+\.\w+|\w+)$", re.IGNORECASE)


class CompanyDomainResolutionService:
    """Resolve company domain with confidence scoring."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def resolve_for_job(self, job: Job) -> ResolvedCompanyDomain:
        if job.company_domain:
            return ResolvedCompanyDomain(
                domain=_normalize_domain(job.company_domain),
                confidence=DomainConfidence.exact_from_posting,
                source="job.company_domain",
            )
        if job.url:
            host = _normalize_domain(urlparse(job.url).hostname or "")
            if host and not _is_job_board_host(host):
                return ResolvedCompanyDomain(
                    domain=host,
                    confidence=DomainConfidence.exact_from_posting,
                    source="job.url",
                )
        company = self._session.query(Company).filter(Company.id == job.company_id).one_or_none()
        if company is not None:
            return self.resolve_for_company(company)
        return ResolvedCompanyDomain(domain=None, confidence=DomainConfidence.unverified, source="none")

    def resolve_for_company(self, company: Company) -> ResolvedCompanyDomain:
        row = (
            self._session.query(CompanyDomain)
            .filter(
                CompanyDomain.company_id == company.id,
                CompanyDomain.status != CompanyDomainStatus.deprecated,
            )
            .order_by(CompanyDomain.created_at.desc())
            .first()
        )
        if row is not None and row.domain:
            conf = (
                DomainConfidence.guessed_and_verified
                if row.status == CompanyDomainStatus.verified
                else DomainConfidence.unverified
            )
            return ResolvedCompanyDomain(
                domain=_normalize_domain(row.domain),
                confidence=conf,
                source="company_domains",
            )
        if company.url:
            host = _normalize_domain(urlparse(company.url).hostname or "")
            if host:
                return ResolvedCompanyDomain(
                    domain=host,
                    confidence=DomainConfidence.unverified,
                    source="company.url",
                )
        return ResolvedCompanyDomain(domain=None, confidence=DomainConfidence.unverified, source="none")

    def ensure_domain_record(
        self,
        company: Company,
        resolved: ResolvedCompanyDomain,
    ) -> None:
        """Persist best-effort domain when missing from company_domains."""
        if not resolved.domain:
            return
        existing = (
            self._session.query(CompanyDomain)
            .filter(
                CompanyDomain.company_id == company.id,
                CompanyDomain.domain == resolved.domain,
            )
            .one_or_none()
        )
        if existing is not None:
            return
        status = (
            CompanyDomainStatus.verified
            if resolved.confidence == DomainConfidence.guessed_and_verified
            else CompanyDomainStatus.unverified
        )
        self._session.add(
            CompanyDomain(
                company_id=company.id,
                domain=resolved.domain,
                status=status,
            )
        )
        self._session.flush()


def domain_from_email(email: str) -> str | None:
    match = _EMAIL_DOMAIN_RE.search(email.strip())
    if not match:
        return None
    return _normalize_domain(match.group(0).lstrip("@"))


def _normalize_domain(value: str) -> str | None:
    text = (value or "").strip().lower()
    text = text.removeprefix("https://").removeprefix("http://")
    text = text.split("/")[0].removeprefix("www.")
    return text or None


def _is_job_board_host(host: str) -> bool:
    boards = (
        "greenhouse.io",
        "lever.co",
        "ashbyhq.com",
        "myworkdayjobs.com",
        "linkedin.com",
        "indeed.com",
    )
    return any(host == b or host.endswith("." + b) for b in boards)
