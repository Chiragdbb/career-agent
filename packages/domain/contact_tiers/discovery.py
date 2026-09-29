"""Tiered contact discovery (-1..3); Tier 4 is manual-only (not invoked here)."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from database.models.enums import (
    CompanyDomainStatus,
    ContactSourceType,
    ContactStatus,
    PeopleRoleStatus,
    PeopleStatus,
)
from database.models.schema import Company, Contact, ContactSource, Job, PeopleRole, Person
from packages.domain.contact_tiers.domain_resolution import CompanyDomainResolutionService
from packages.domain.exceptions import NotFoundError
from packages.domain.provider_usage import ProviderUsageContext, ProviderUsageService
from packages.providers.base import UsageInfo
from packages.providers.email_finder import EmailFinderProvider, EmailFindRequest
from packages.providers.email_verifier import (
    EmailVerificationStatus,
    EmailVerifierProvider,
    EmailVerifyRequest,
)
from packages.providers.people import PeopleProvider, PeopleSearchRequest
from packages.providers.playwright_contacts import PlaywrightContactsProvider, ScrapedContactHit
from packages.providers.search import SearchProvider, SearchRequest


@dataclass(frozen=True)
class ContactDiscoveryResult:
    contact: Contact | None
    tier_reached: int  # -1..3; 4 manual only
    cache_hit: bool


class ContactDiscoveryService:
    """find_or_enrich_contact with spec tier ordering."""

    def __init__(
        self,
        session: Session,
        user_id: uuid.UUID,
        *,
        people: PeopleProvider | None = None,
        email_finder: EmailFinderProvider | None = None,
        email_verifier: EmailVerifierProvider | None = None,
        playwright_contacts: PlaywrightContactsProvider | None = None,
        search: SearchProvider | None = None,
        usage: ProviderUsageService | None = None,
        staleness_days: int = 120,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._people = people
        self._email_finder = email_finder
        self._email_verifier = email_verifier
        self._playwright = playwright_contacts
        self._search = search
        self._usage = usage or ProviderUsageService(session)
        self._staleness_days = staleness_days
        self._context = ProviderUsageContext(user_id=user_id)
        self._domains = CompanyDomainResolutionService(session)

    def find_or_enrich_contact(
        self,
        company_id: uuid.UUID,
        *,
        job: Job | None = None,
    ) -> ContactDiscoveryResult:
        company = self._session.query(Company).filter(Company.id == company_id).one_or_none()
        if company is None:
            raise NotFoundError("Company not found")

        # Tier -1: cache
        cached = self._fresh_cached_contact(company_id)
        self._log_tier(-1, company_id, success=cached is not None, cache_hit=cached is not None)
        if cached is not None:
            cached.tier_reached = -1
            return ContactDiscoveryResult(contact=cached, tier_reached=-1, cache_hit=True)

        resolved = self._domains.resolve_for_company(company)
        if job is not None:
            resolved = self._domains.resolve_for_job(job)
        self._domains.ensure_domain_record(company, resolved)
        domain = resolved.domain

        if not domain or resolved.confidence.value == "unverified":
            self._log_tier(-1, company_id, success=False, extra={"reason": "domain_unverified"})
            # Continue with best-effort domain if present

        # Tier 0: job posting signals
        if job is not None:
            hit = self._tier0_from_job(job, company)
            if hit is not None:
                contact = self._persist_hit(company, hit, source="job_posting", tier=0)
                return ContactDiscoveryResult(contact=contact, tier_reached=0, cache_hit=False)

        # Tier 1: company pages (Scrapling/Playwright contacts provider)
        if domain and self._playwright is not None:
            hit = self._tier1_company_pages(company, domain)
            if hit is not None:
                contact = self._persist_hit(company, hit, source="playwright", tier=1)
                return ContactDiscoveryResult(contact=contact, tier_reached=1, cache_hit=False)

        # Tier 2: search-backed public snippets
        if self._search is not None and domain:
            hit = self._tier2_search(company, domain, job_title=job.title if job else None)
            if hit is not None:
                contact = self._persist_hit(company, hit, source="web_search", tier=2)
                contact = self._tier25_pattern_email(contact, company, domain) or contact
                return ContactDiscoveryResult(contact=contact, tier_reached=2, cache_hit=False)

        # Tier 3: Hunter then Apollo (paid)
        paid = self._tier3_hunter_then_apollo(company, domain, job_title=job.title if job else None)
        if paid is not None:
            contact, sub = paid
            contact.tier_reached = 3
            return ContactDiscoveryResult(contact=contact, tier_reached=3, cache_hit=False)

        return ContactDiscoveryResult(contact=None, tier_reached=3, cache_hit=False)

    def _tier0_from_job(self, job: Job, company: Company) -> ScrapedContactHit | None:
        details = job.details if isinstance(job.details, dict) else {}
        for key in ("contact_email", "recruiter_email"):
            raw = details.get(key)
            if isinstance(raw, str) and "@" in raw:
                return ScrapedContactHit(
                    full_name="Hiring contact",
                    title="Recruiter",
                    email=raw.strip().lower(),
                    email_confidence="unverified",
                    source_url=job.url,
                )
        if job.description:
            mailto = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", job.description)
            if mailto:
                return ScrapedContactHit(
                    full_name="Hiring contact",
                    title="Recruiter",
                    email=mailto.group(0).lower(),
                    email_confidence="unverified",
                    source_url=job.url,
                )
        return None

    def _tier1_company_pages(self, company: Company, domain: str) -> ScrapedContactHit | None:
        assert self._playwright is not None
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
                tier_reached=1,
            )
        except Exception as exc:
            self._log_tier(1, company.id, success=False, error=str(exc))
            return None
        if not result.contacts:
            self._log_tier(1, company.id, success=False)
            return None
        return result.contacts[0]

    def _tier2_search(
        self,
        company: Company,
        domain: str,
        *,
        job_title: str | None,
    ) -> ScrapedContactHit | None:
        assert self._search is not None
        title_hint = job_title or "software engineer"
        query = f'"{company.name}" recruiter "{title_hint}" site:linkedin.com/in'
        try:
            response = self._search.search(SearchRequest(query=query, max_results=5))
            self._usage.record(
                context=self._context,
                provider_name=self._search.metadata.name,
                operation="contact_lookup",
                usage=response.usage,
                success=bool(response.results),
                related_entity_type="company",
                related_entity_id=company.id,
                tier_reached=2,
            )
        except Exception as exc:
            self._log_tier(2, company.id, success=False, error=str(exc))
            return None
        if not response.results:
            return None
        best = response.results[0]
        name = _name_from_snippet(best.title, best.snippet)
        return ScrapedContactHit(
            full_name=name or "LinkedIn profile",
            title="Recruiter",
            email=None,
            email_confidence="unverified",
            source_url=str(best.url),
        )

    def _tier25_pattern_email(
        self,
        contact: Contact,
        company: Company,
        domain: str,
    ) -> Contact | None:
        """Infer email from known verified pattern on domain."""
        if not contact.name or self._email_finder is None:
            return None
        verified = (
            self._session.query(Contact)
            .filter(
                Contact.user_id == self._user_id,
                Contact.company_id == company.id,
                Contact.confidence == "verified",
            )
            .first()
        )
        if verified is None:
            return None
        meta_rows = (
            self._session.query(ContactSource)
            .filter(ContactSource.contact_id == verified.id)
            .all()
        )
        pattern_email = None
        for row in meta_rows:
            meta = row.metadata_json if isinstance(row.metadata_json, dict) else {}
            em = meta.get("email")
            if isinstance(em, str) and em.endswith("@" + domain):
                pattern_email = em
                break
        if not pattern_email:
            return None
        local = pattern_email.split("@", 1)[0]
        if "." in local:
            sep = "."
        elif "_" in local:
            sep = "_"
        else:
            return None
        parts = contact.name.lower().split()
        if len(parts) < 2:
            return None
        guess = f"{parts[0]}{sep}{parts[-1]}@{domain}"
        if self._email_verifier is not None:
            try:
                vr = self._email_verifier.verify(EmailVerifyRequest(email=guess))
                if vr.status != EmailVerificationStatus.valid:
                    return None
            except Exception:
                return None
        contact.confidence = "guessed"
        return contact

    def _tier3_hunter_then_apollo(
        self,
        company: Company,
        domain: str | None,
        *,
        job_title: str | None,
    ) -> tuple[Contact, str] | None:
        if domain and self._email_finder is not None:
            try:
                found = self._email_finder.find_email(
                    EmailFindRequest(
                        full_name=f"{company.name} Recruiter",
                        company_domain=domain,
                        company_name=company.name,
                    )
                )
                candidates = [c for c in found.candidates if c.email and "@" in c.email]
                self._log_tier(3, company.id, success=bool(candidates), extra={"sub": "hunter"})
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
                    contact = self._persist_hit(company, hit, source="hunter", tier=3)
                    return contact, "hunter"
            except Exception as exc:
                self._log_tier(3, company.id, success=False, error=str(exc), extra={"sub": "hunter"})

        if self._people is not None:
            try:
                titles = ["recruiter", "talent acquisition"]
                if job_title:
                    titles = [f"{job_title} recruiter", *titles]
                response = self._people.search_people(
                    PeopleSearchRequest(
                        company_name=company.name,
                        company_domain=domain,
                        titles=titles,
                        max_results=3,
                    )
                )
                self._log_tier(3, company.id, success=bool(response.people), extra={"sub": "apollo"})
                if response.people:
                    person = response.people[0]
                    hit = ScrapedContactHit(
                        full_name=person.full_name,
                        title=person.title,
                        email=None,
                        email_confidence="unverified",
                        source_url=str(person.linkedin_url) if person.linkedin_url else None,
                    )
                    contact = self._persist_hit(company, hit, source="apollo", tier=3)
                    if domain and self._email_finder is not None and contact.name:
                        self._maybe_hunter_email(contact, company, domain)
                    return contact, "apollo"
            except Exception as exc:
                self._log_tier(3, company.id, success=False, error=str(exc), extra={"sub": "apollo"})
        return None

    def _maybe_hunter_email(self, contact: Contact, company: Company, domain: str) -> None:
        if self._email_finder is None or not contact.name:
            return
        try:
            found = self._email_finder.find_email(
                EmailFindRequest(
                    full_name=contact.name,
                    company_domain=domain,
                    company_name=company.name,
                )
            )
            for cand in found.candidates:
                if cand.email:
                    meta = ContactSource(
                        id=uuid.uuid4(),
                        user_id=self._user_id,
                        contact_id=contact.id,
                        source_type=ContactSourceType.provider_api,
                        metadata_json={"email": cand.email, "source": "hunter", "enrich": True},
                    )
                    self._session.add(meta)
                    break
        except Exception:
            return

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

    def _persist_hit(
        self,
        company: Company,
        hit: ScrapedContactHit,
        *,
        source: str,
        tier: int,
    ) -> Contact:
        now = datetime.now(timezone.utc)
        person = Person(id=uuid.uuid4(), name=hit.full_name, status=PeopleStatus.active)
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
            confidence=hit.email_confidence if hit.email else "unverified",
            last_verified_at=now,
            tier_reached=tier,
        )
        self._session.add(contact)
        self._session.flush()
        source_type = (
            ContactSourceType.scrape
            if source in ("playwright", "job_posting", "web_search")
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
                    "email": hit.email,
                    "tier": tier,
                    "discovered_at": now.isoformat(),
                },
            )
        )
        self._session.flush()
        return contact

    def _log_tier(
        self,
        tier: int,
        company_id: uuid.UUID,
        *,
        success: bool,
        cache_hit: bool = False,
        error: str | None = None,
        extra: dict | None = None,
    ) -> None:
        payload = {"tier": tier, "cache_hit": cache_hit, **(extra or {})}
        self._usage.record(
            context=self._context,
            provider_name="contact-discovery",
            operation="contact_lookup",
            usage=UsageInfo(
                operation="contact_lookup",
                unit_type="requests",
                units=1.0,
                provider="contact-discovery",
                extra=payload,
            ),
            success=success,
            error=error,
            related_entity_type="company",
            related_entity_id=company_id,
            tier_reached=tier,
        )


def _name_from_snippet(title: str, snippet: str) -> str | None:
    for text in (title, snippet):
        cleaned = text.split("|")[0].split("-")[0].strip()
        if cleaned and len(cleaned.split()) <= 5:
            return cleaned
    return None
