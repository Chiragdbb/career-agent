"""Tiered contact resolution: DB cache → Playwright (company pages) → paid APIs."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from database.models.enums import (
    CompanyDomainStatus,
    ContactSourceType,
    ContactStatus,
    PeopleRoleStatus,
    PeopleStatus,
)
from database.models.schema import (
    Company,
    CompanyDomain,
    Contact,
    ContactSource,
    PeopleRole,
    Person,
)
from packages.domain.exceptions import NotFoundError
from packages.domain.provider_usage import ProviderUsageContext, ProviderUsageService
from packages.providers.base import UsageInfo
from packages.providers.email_finder import EmailFinderProvider, EmailFindRequest
from packages.providers.people import PeopleProvider, PeopleSearchRequest
from packages.providers.playwright_contacts import (
    MockPlaywrightContactsProvider,
    PlaywrightContactsProvider,
    ScrapedContactHit,
)


def contact_staleness_days() -> int:
    raw = (os.getenv("CONTACT_STALENESS_DAYS") or "120").strip()
    try:
        return max(30, min(int(raw), 365))
    except ValueError:
        return 120


@dataclass(frozen=True)
class ContactResolveResult:
    contact: Contact | None
    tier: str  # cache | playwright | apollo | hunter | none
    cache_hit: bool


class ContactEnrichmentService:
    """find_or_enrich_contact — short-circuits on first successful tier."""

    def __init__(
        self,
        session: Session,
        user_id: uuid.UUID,
        *,
        people: PeopleProvider | None = None,
        email_finder: EmailFinderProvider | None = None,
        playwright_contacts: PlaywrightContactsProvider | MockPlaywrightContactsProvider | None = None,
        usage: ProviderUsageService | None = None,
        staleness_days: int | None = None,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._people = people
        self._email_finder = email_finder
        self._playwright = playwright_contacts
        self._usage = usage or ProviderUsageService(session)
        self._staleness_days = staleness_days if staleness_days is not None else contact_staleness_days()
        self._context = ProviderUsageContext(user_id=user_id)

    def find_or_enrich_contact(self, company_id: uuid.UUID) -> ContactResolveResult:
        company = self._session.query(Company).filter(Company.id == company_id).one_or_none()
        if company is None:
            raise NotFoundError("Company not found")

        # Tier 1: DB cache (non-stale)
        cached = self._fresh_cached_contact(company_id)
        self._log_attempt(
            provider="db-cache",
            operation="contact_lookup",
            success=cached is not None,
            related_entity_id=company_id,
            extra={"tier": "cache", "cache_hit": cached is not None},
        )
        if cached is not None:
            return ContactResolveResult(contact=cached, tier="cache", cache_hit=True)

        domain = self._company_domain(company)

        # Tier 2: Playwright on company-owned pages only
        playwright_hit = self._try_playwright(company, domain)
        if playwright_hit is not None:
            return ContactResolveResult(contact=playwright_hit, tier="playwright", cache_hit=False)

        # Tier 3: Apollo / Hunter paid APIs
        paid = self._try_paid_apis(company, domain)
        if paid is not None:
            return ContactResolveResult(contact=paid[0], tier=paid[1], cache_hit=False)

        return ContactResolveResult(contact=None, tier="none", cache_hit=False)

    def _fresh_cached_contact(self, company_id: uuid.UUID) -> Contact | None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._staleness_days)
        rows = (
            self._session.query(Contact)
            .filter(Contact.user_id == self._user_id, Contact.company_id == company_id)
            .order_by(Contact.last_verified_at.desc().nullslast(), Contact.updated_at.desc())
            .all()
        )
        for row in rows:
            verified_at = row.last_verified_at or row.updated_at
            if verified_at is None:
                continue
            if verified_at.tzinfo is None:
                verified_at = verified_at.replace(tzinfo=timezone.utc)
            if verified_at >= cutoff and (row.name or row.title):
                return row
        return None

    def _try_playwright(self, company: Company, domain: str | None) -> Contact | None:
        if not domain or self._playwright is None:
            self._log_attempt(
                provider="playwright",
                operation="contact_lookup",
                success=False,
                related_entity_id=company.id,
                extra={"tier": "playwright", "reason": "no_domain_or_provider"},
            )
            return None
        try:
            result = self._playwright.find_contacts(company_domain=domain)
            self._usage.record(
                context=self._context,
                provider_name=self._playwright.metadata.name,
                operation="contact_lookup",
                usage=result.usage,
                success=bool(result.contacts),
                related_entity_type="company",
                related_entity_id=company.id,
            )
        except Exception as exc:
            self._log_attempt(
                provider="playwright",
                operation="contact_lookup",
                success=False,
                related_entity_id=company.id,
                error=str(exc),
                extra={"tier": "playwright"},
            )
            return None

        if not result.contacts:
            return None

        hit = result.contacts[0]
        return self._persist_hit(
            company=company,
            hit=hit,
            source="playwright",
            confidence=hit.email_confidence if hit.email else "unverified",
        )

    def _try_paid_apis(
        self,
        company: Company,
        domain: str | None,
    ) -> tuple[Contact, str] | None:
        # Apollo people search
        if self._people is not None:
            try:
                response = self._people.search_people(
                    PeopleSearchRequest(
                        company_name=company.name,
                        company_domain=domain,
                        titles=["recruiter", "talent acquisition", "hiring manager"],
                        max_results=3,
                    )
                )
                self._log_attempt(
                    provider=self._people.metadata.name,
                    operation="contact_lookup",
                    success=bool(response.people),
                    related_entity_id=company.id,
                    extra={"tier": "apollo"},
                )
                if response.people:
                    person = response.people[0]
                    hit = ScrapedContactHit(
                        full_name=person.full_name,
                        title=person.title,
                        email=None,
                        email_confidence="unverified",
                        source_url=str(person.linkedin_url) if person.linkedin_url else None,
                    )
                    contact = self._persist_hit(
                        company=company,
                        hit=hit,
                        source="apollo",
                        confidence="unverified",
                    )
                    # Optional Hunter email enrichment after Apollo name
                    if domain and self._email_finder is not None and contact.name:
                        self._maybe_hunter_email(contact, company, domain)
                    return contact, "apollo"
            except Exception as exc:
                self._log_attempt(
                    provider=getattr(self._people, "metadata", None) and self._people.metadata.name or "apollo",
                    operation="contact_lookup",
                    success=False,
                    related_entity_id=company.id,
                    error=str(exc),
                    extra={"tier": "apollo"},
                )

        # Hunter-only path when Apollo unavailable
        if domain and self._email_finder is not None:
            try:
                found = self._email_finder.find_email(
                    EmailFindRequest(
                        full_name=company.name + " Recruiter",
                        company_domain=domain,
                        company_name=company.name,
                    )
                )
                # Never invent — only use provider candidates.
                candidates = [c for c in found.candidates if c.email and "@" in c.email]
                self._log_attempt(
                    provider=self._email_finder.metadata.name,
                    operation="contact_lookup",
                    success=bool(candidates),
                    related_entity_id=company.id,
                    extra={"tier": "hunter"},
                )
                if candidates:
                    best = max(candidates, key=lambda c: c.confidence)
                    local = best.email.split("@", 1)[0]
                    name = local.replace(".", " ").replace("_", " ").title()
                    hit = ScrapedContactHit(
                        full_name=name,
                        title="Recruiter",
                        email=best.email.lower(),
                        email_confidence="unverified",
                    )
                    contact = self._persist_hit(
                        company=company,
                        hit=hit,
                        source="hunter",
                        confidence="unverified",
                    )
                    return contact, "hunter"
            except Exception as exc:
                self._log_attempt(
                    provider="hunter",
                    operation="contact_lookup",
                    success=False,
                    related_entity_id=company.id,
                    error=str(exc),
                    extra={"tier": "hunter"},
                )

        return None

    def _maybe_hunter_email(self, contact: Contact, company: Company, domain: str) -> None:
        assert self._email_finder is not None
        try:
            found = self._email_finder.find_email(
                EmailFindRequest(
                    full_name=contact.name or "",
                    company_domain=domain,
                    company_name=company.name,
                )
            )
            self._log_attempt(
                provider=self._email_finder.metadata.name,
                operation="contact_lookup",
                success=bool(found.candidates),
                related_entity_id=company.id,
                extra={"tier": "hunter", "enrich": True},
            )
        except Exception as exc:
            self._log_attempt(
                provider="hunter",
                operation="contact_lookup",
                success=False,
                related_entity_id=company.id,
                error=str(exc),
                extra={"tier": "hunter", "enrich": True},
            )

    def _persist_hit(
        self,
        *,
        company: Company,
        hit: ScrapedContactHit,
        source: str,
        confidence: str,
    ) -> Contact:
        now = datetime.now(timezone.utc)
        person = Person(
            id=uuid.uuid4(),
            name=hit.full_name,
            linkedin_url=None,
            status=PeopleStatus.active,
        )
        self._session.add(person)
        self._session.flush()
        self._session.add(
            PeopleRole(
                id=uuid.uuid4(),
                people_id=person.id,
                company_id=company.id,
                status=PeopleRoleStatus.current,
                role_title=hit.title,
            )
        )
        contact = Contact(
            id=uuid.uuid4(),
            user_id=self._user_id,
            people_id=person.id,
            company_id=company.id,
            status=ContactStatus.identified,
            name=hit.full_name,
            title=hit.title,
            source=source,
            confidence=confidence,
            last_verified_at=now,
        )
        self._session.add(contact)
        self._session.flush()
        source_type = (
            ContactSourceType.scrape
            if source == "playwright"
            else ContactSourceType.provider_api
        )
        self._session.add(
            ContactSource(
                id=uuid.uuid4(),
                user_id=self._user_id,
                contact_id=contact.id,
                source_type=source_type,
                source_url=hit.source_url,
                metadata_json={
                    "source": source,
                    "confidence": confidence,
                    "email": hit.email,
                    "discovered_at": now.isoformat(),
                },
            )
        )
        self._session.flush()
        return contact

    def _company_domain(self, company: Company) -> str | None:
        row = (
            self._session.query(CompanyDomain)
            .filter(
                CompanyDomain.company_id == company.id,
                CompanyDomain.status != CompanyDomainStatus.deprecated,
            )
            .order_by(CompanyDomain.created_at.desc())
            .first()
        )
        if row is not None:
            return row.domain
        if company.url:
            host = (urlparse(company.url).hostname or "").removeprefix("www.")
            return host or None
        return None

    def _log_attempt(
        self,
        *,
        provider: str,
        operation: str,
        success: bool,
        related_entity_id: uuid.UUID | None,
        error: str | None = None,
        extra: dict | None = None,
    ) -> None:
        self._usage.record(
            context=self._context,
            provider_name=provider,
            operation=operation,
            usage=UsageInfo(
                operation=operation,
                unit_type="requests",
                units=1.0,
                estimated_cost_usd=0.0 if provider in ("db-cache", "playwright") else None,
                provider=provider,
                extra=extra or {},
            ),
            success=success,
            error=error,
            related_entity_type="company",
            related_entity_id=related_entity_id,
        )


def find_or_enrich_contact(
    session: Session,
    user_id: uuid.UUID,
    company_id: uuid.UUID,
    **kwargs: object,
) -> ContactResolveResult:
    """Module-level entrypoint matching the spec name."""
    return ContactEnrichmentService(session, user_id, **kwargs).find_or_enrich_contact(company_id)  # type: ignore[arg-type]
