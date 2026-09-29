"""Contact enrichment — delegates to tiered ContactDiscoveryService."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from database.models.schema import Contact, Job
from packages.domain.contact_tiers.discovery import ContactDiscoveryResult, ContactDiscoveryService
from packages.domain.exceptions import NotFoundError
from packages.domain.provider_usage import ProviderUsageService
from packages.providers.email_finder import EmailFinderProvider
from packages.providers.people import PeopleProvider
from packages.providers.playwright_contacts import MockPlaywrightContactsProvider, PlaywrightContactsProvider
from packages.providers.search import SearchProvider


def contact_staleness_days() -> int:
    raw = (os.getenv("CONTACT_STALENESS_DAYS") or "120").strip()
    try:
        return max(30, min(int(raw), 365))
    except ValueError:
        return 120


@dataclass(frozen=True)
class ContactResolveResult:
    contact: Contact | None
    tier: str
    cache_hit: bool


_TIER_LABELS = {
    -1: "cache",
    0: "job_posting",
    1: "playwright",
    2: "web_search",
    3: "paid_api",
}


class ContactEnrichmentService:
    """Spec entrypoint — wraps ContactDiscoveryService."""

    def __init__(
        self,
        session: Session,
        user_id: uuid.UUID,
        *,
        people: PeopleProvider | None = None,
        email_finder: EmailFinderProvider | None = None,
        playwright_contacts: PlaywrightContactsProvider | MockPlaywrightContactsProvider | None = None,
        search: SearchProvider | None = None,
        usage: ProviderUsageService | None = None,
        staleness_days: int | None = None,
    ) -> None:
        self._discovery = ContactDiscoveryService(
            session,
            user_id,
            people=people,
            email_finder=email_finder,
            playwright_contacts=playwright_contacts,
            search=search,
            usage=usage,
            staleness_days=staleness_days if staleness_days is not None else contact_staleness_days(),
        )

    def find_or_enrich_contact(
        self,
        company_id: uuid.UUID,
        *,
        job: Job | None = None,
    ) -> ContactResolveResult:
        result = self._discovery.find_or_enrich_contact(company_id, job=job)
        return ContactResolveResult(
            contact=result.contact,
            tier=_TIER_LABELS.get(result.tier_reached, str(result.tier_reached)),
            cache_hit=result.cache_hit,
        )


def find_or_enrich_contact(
    session: Session,
    user_id: uuid.UUID,
    company_id: uuid.UUID,
    **kwargs: object,
) -> ContactResolveResult:
    job = kwargs.pop("job", None)
    service = ContactEnrichmentService(session, user_id, **kwargs)  # type: ignore[arg-type]
    return service.find_or_enrich_contact(company_id, job=job if isinstance(job, Job) else None)
