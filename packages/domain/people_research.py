"""PeopleResearchService — discover contacts by role priority.

Priority: recruiter → role recruiter → hiring manager → eng manager → employee → referral.
Never invent email addresses. Never mark verified without EmailVerifierProvider evidence.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from database.models.enums import (
    CompanyDomainStatus,
    ContactSourceType,
    ContactStatus,
    EmailVerificationStatus,
    PeopleRoleStatus,
    PeopleStatus,
)
from database.models.schema import (
    Company,
    CompanyDomain,
    Contact,
    ContactSource,
    EmailVerification,
    Job,
    PeopleRole,
    Person,
)
from packages.domain.exceptions import NotFoundError
from packages.domain.people_models import (
    ROLE_PRIORITY_ORDER,
    ROLE_TITLE_KEYWORDS,
    DiscoveredPerson,
    PeopleResearchResult,
    RolePriority,
)
from packages.providers.email_finder import EmailFinderProvider, EmailFindRequest
from packages.providers.email_verifier import (
    EmailVerificationStatus as ProviderEmailStatus,
    EmailVerifierProvider,
    EmailVerifyRequest,
)
from packages.providers.people import PeopleProvider, PeopleSearchRequest, PersonHit


class PeopleResearchService:
    """Find and persist people for a company/job using PeopleProvider (+ optional email)."""

    def __init__(
        self,
        session: Session,
        user_id: uuid.UUID,
        *,
        people: PeopleProvider,
        email_finder: EmailFinderProvider | None = None,
        email_verifier: EmailVerifierProvider | None = None,
        enrich_emails: bool = False,
        max_per_role: int = 5,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._people = people
        self._email_finder = email_finder
        self._email_verifier = email_verifier
        self._enrich_emails = enrich_emails
        self._max_per_role = max_per_role

    def research_for_job(
        self,
        job_id: uuid.UUID,
        *,
        department: str | None = None,
        enrich_emails: bool | None = None,
    ) -> PeopleResearchResult:
        job = self._session.query(Job).filter(Job.id == job_id).one_or_none()
        if job is None:
            raise NotFoundError("Job not found")
        return self.research_company(
            job.company_id,
            job_title=job.title,
            job_id=job.id,
            department=department,
            enrich_emails=enrich_emails,
        )

    def research_company(
        self,
        company_id: uuid.UUID,
        *,
        job_title: str | None = None,
        job_id: uuid.UUID | None = None,
        department: str | None = None,
        enrich_emails: bool | None = None,
    ) -> PeopleResearchResult:
        company = self._session.query(Company).filter(Company.id == company_id).one_or_none()
        if company is None:
            raise NotFoundError("Company not found")

        do_enrich = self._enrich_emails if enrich_emails is None else enrich_emails
        domain = self._company_domain(company)
        discovered_at = datetime.now(timezone.utc)
        results: list[DiscoveredPerson] = []
        seen_names: set[str] = set()

        for role in ROLE_PRIORITY_ORDER:
            titles = list(ROLE_TITLE_KEYWORDS[role])
            if role == RolePriority.role_recruiter and job_title:
                titles = [f"{job_title} recruiter", *titles]
            if department and role in (
                RolePriority.hiring_manager,
                RolePriority.engineering_manager,
                RolePriority.employee,
            ):
                titles = [f"{department} {t}" for t in titles[:2]] + titles

            try:
                response = self._people.search_people(
                    PeopleSearchRequest(
                        company_name=company.name,
                        company_domain=domain,
                        titles=titles[:6],
                        max_results=self._max_per_role,
                    )
                )
            except Exception:
                continue

            provider_name = self._people.metadata.name
            for hit in response.people:
                key = (hit.full_name or "").strip().lower()
                if not key or key in seen_names:
                    continue
                seen_names.add(key)

                classified = classify_role(hit.title) or role
                confidence = _confidence_for_hit(hit, classified)
                person_row, contact = self._persist_person(
                    company=company,
                    hit=hit,
                    relevance=classified,
                    confidence=confidence,
                    provider=provider_name,
                    discovered_at=discovered_at,
                )

                email: str | None = None
                email_verified = False
                email_status: str | None = None
                if do_enrich and domain and self._email_finder is not None:
                    email, email_verified, email_status = self._maybe_enrich_email(
                        contact=contact,
                        full_name=hit.full_name,
                        company_domain=domain,
                        company_name=company.name,
                    )

                results.append(
                    DiscoveredPerson(
                        name=hit.full_name,
                        title=hit.title,
                        company=hit.company_name or company.name,
                        location=hit.location,
                        source="people_provider",
                        relevance=classified,
                        confidence=confidence,
                        provider=provider_name,
                        discovered_at=discovered_at,
                        linkedin_url=str(hit.linkedin_url) if hit.linkedin_url else None,
                        email=email,
                        email_verified=email_verified,
                        email_verification_status=email_status,
                        people_id=person_row.id,
                        contact_id=contact.id,
                    )
                )

        self._session.commit()
        results.sort(key=lambda p: (ROLE_PRIORITY_ORDER.index(p.relevance), -p.confidence))
        return PeopleResearchResult(
            company_id=company.id,
            company_name=company.name,
            job_id=job_id,
            job_title=job_title,
            people=results,
            searched_roles=list(ROLE_PRIORITY_ORDER),
        )

    def list_contacts_for_company(self, company_id: uuid.UUID) -> list[Contact]:
        return (
            self._session.query(Contact)
            .filter(Contact.user_id == self._user_id, Contact.company_id == company_id)
            .order_by(Contact.created_at.desc())
            .all()
        )

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
            host = urlparse(company.url).hostname or ""
            host = host.removeprefix("www.")
            return host or None
        return None

    def _persist_person(
        self,
        *,
        company: Company,
        hit: PersonHit,
        relevance: RolePriority,
        confidence: float,
        provider: str,
        discovered_at: datetime,
    ) -> tuple[Person, Contact]:
        linkedin = str(hit.linkedin_url) if hit.linkedin_url else None
        person = None
        if linkedin:
            person = (
                self._session.query(Person)
                .filter(Person.linkedin_url == linkedin)
                .one_or_none()
            )
        if person is None:
            person = Person(
                id=uuid.uuid4(),
                name=hit.full_name,
                linkedin_url=linkedin,
                status=PeopleStatus.active,
            )
            self._session.add(person)
            self._session.flush()

        existing_role = (
            self._session.query(PeopleRole)
            .filter(
                PeopleRole.people_id == person.id,
                PeopleRole.company_id == company.id,
                PeopleRole.status == PeopleRoleStatus.current,
            )
            .one_or_none()
        )
        if existing_role is None:
            self._session.add(
                PeopleRole(
                    id=uuid.uuid4(),
                    people_id=person.id,
                    company_id=company.id,
                    status=PeopleRoleStatus.current,
                    role_title=hit.title,
                )
            )
        elif hit.title and not existing_role.role_title:
            existing_role.role_title = hit.title

        contact = (
            self._session.query(Contact)
            .filter(
                Contact.user_id == self._user_id,
                Contact.people_id == person.id,
                Contact.company_id == company.id,
            )
            .one_or_none()
        )
        if contact is None:
            contact = Contact(
                id=uuid.uuid4(),
                user_id=self._user_id,
                people_id=person.id,
                company_id=company.id,
                status=ContactStatus.identified,
                name=hit.full_name,
                title=hit.title,
            )
            self._session.add(contact)
            self._session.flush()
        else:
            contact.name = hit.full_name
            if hit.title:
                contact.title = hit.title

        self._session.add(
            ContactSource(
                id=uuid.uuid4(),
                user_id=self._user_id,
                contact_id=contact.id,
                source_type=ContactSourceType.provider_api,
                source_url=linkedin,
                metadata_json={
                    "relevance": relevance.value,
                    "confidence": confidence,
                    "provider": provider,
                    "discovered_at": discovered_at.isoformat(),
                    "location": hit.location,
                    "title": hit.title,
                    "company": hit.company_name or company.name,
                },
            )
        )
        self._session.flush()
        return person, contact

    def _maybe_enrich_email(
        self,
        *,
        contact: Contact,
        full_name: str,
        company_domain: str,
        company_name: str,
    ) -> tuple[str | None, bool, str | None]:
        """Find + optionally verify email. Never invent; never mark verified without evidence."""
        assert self._email_finder is not None
        try:
            found = self._email_finder.find_email(
                EmailFindRequest(
                    full_name=full_name,
                    company_domain=company_domain,
                    company_name=company_name,
                )
            )
        except Exception:
            return None, False, None

        if not found.candidates:
            return None, False, None

        # Take highest-confidence candidate from provider only — never synthesize.
        candidate = max(found.candidates, key=lambda c: c.confidence)
        email = (candidate.email or "").strip().lower()
        if not email or "@" not in email:
            return None, False, None

        status = EmailVerificationStatus.pending
        verified = False
        details: dict = {
            "sources": candidate.sources,
            "finder_confidence": candidate.confidence,
            "finder_provider": self._email_finder.metadata.name,
        }

        if self._email_verifier is not None:
            try:
                verified_resp = self._email_verifier.verify_email(
                    EmailVerifyRequest(email=email)
                )
                status = _map_provider_email_status(verified_resp.status)
                details["verifier_provider"] = self._email_verifier.metadata.name
                details["verifier_score"] = verified_resp.score
                details["verifier_details"] = verified_resp.details
                # Only mark verified with explicit valid evidence from verifier.
                if verified_resp.status == ProviderEmailStatus.valid:
                    verified = True
                    status = EmailVerificationStatus.verified
                    contact.status = ContactStatus.verified
            except Exception as exc:
                details["verifier_error"] = str(exc)
                status = EmailVerificationStatus.unknown

        self._session.add(
            EmailVerification(
                id=uuid.uuid4(),
                user_id=self._user_id,
                contact_id=contact.id,
                email=email,
                status=status,
                verified_at=datetime.now(timezone.utc) if verified else None,
                details=details,
            )
        )
        self._session.flush()
        return email, verified, status.value


def classify_role(title: str | None) -> RolePriority | None:
    if not title:
        return None
    lowered = title.lower()
    # Check more specific roles first.
    for role in (
        RolePriority.role_recruiter,
        RolePriority.recruiter,
        RolePriority.engineering_manager,
        RolePriority.hiring_manager,
        RolePriority.referral,
        RolePriority.employee,
    ):
        for keyword in ROLE_TITLE_KEYWORDS[role]:
            if keyword.strip().lower() in lowered:
                return role
    return None


def _confidence_for_hit(hit: PersonHit, relevance: RolePriority) -> float:
    base = 0.55
    if hit.title:
        base += 0.15
    if hit.linkedin_url:
        base += 0.15
    if hit.location:
        base += 0.05
    # Prefer higher-priority roles slightly when title matches that role.
    index = ROLE_PRIORITY_ORDER.index(relevance)
    base += max(0.0, (5 - index) * 0.02)
    return round(min(base, 0.95), 2)


def _map_provider_email_status(status: ProviderEmailStatus) -> EmailVerificationStatus:
    mapping = {
        ProviderEmailStatus.valid: EmailVerificationStatus.verified,
        ProviderEmailStatus.invalid: EmailVerificationStatus.invalid,
        ProviderEmailStatus.risky: EmailVerificationStatus.catch_all,
        ProviderEmailStatus.unknown: EmailVerificationStatus.unknown,
    }
    return mapping.get(status, EmailVerificationStatus.unknown)
