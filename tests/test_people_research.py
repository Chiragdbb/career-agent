"""STEP 16 — PeopleResearchService with mocked Apollo/Hunter providers."""

from __future__ import annotations

import uuid

import pytest

from database.models.enums import (
    CompanyDomainStatus,
    CompanyStatus,
    ContactStatus,
    EmailVerificationStatus,
    UserStatus,
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
    User,
)
from packages.domain.people_models import RolePriority
from packages.domain.people_research import PeopleResearchService, classify_role
from packages.providers.email_finder import EmailCandidate, MockEmailFinderProvider
from packages.providers.email_verifier import (
    EmailVerificationStatus as ProviderEmailStatus,
    MockEmailVerifierProvider,
)
from packages.providers.exceptions import ProviderNotConfiguredError
from packages.providers.people import MockPeopleProvider, PersonHit
from packages.providers.apollo_people import ApolloPeopleProvider
from packages.providers.hunter_email import HunterEmailFinderProvider


def _session():
    from app.database import get_session_factory

    return get_session_factory()()


@pytest.fixture
def people_ctx():
    session = _session()
    user = User(id=uuid.uuid4(), auth_subject=f"people-{uuid.uuid4()}", status=UserStatus.active)
    company = Company(
        id=uuid.uuid4(),
        name="People Target Co",
        url="https://people-target.example",
        status=CompanyStatus.active,
    )
    domain = CompanyDomain(
        id=uuid.uuid4(),
        company_id=company.id,
        domain="people-target.example",
        status=CompanyDomainStatus.verified,
    )
    job = Job(
        id=uuid.uuid4(),
        company_id=company.id,
        title="Senior Backend Engineer",
        url=f"https://people-target.example/jobs/{uuid.uuid4()}",
    )
    session.add_all([user, company, domain, job])
    session.commit()
    try:
        yield session, user, company, job
    finally:
        people_ids = [
            row.people_id
            for row in session.query(Contact).filter(Contact.user_id == user.id).all()
        ]
        session.query(EmailVerification).filter(EmailVerification.user_id == user.id).delete()
        session.query(ContactSource).filter(ContactSource.user_id == user.id).delete()
        session.query(Contact).filter(Contact.user_id == user.id).delete()
        if people_ids:
            session.query(PeopleRole).filter(PeopleRole.people_id.in_(people_ids)).delete(
                synchronize_session=False
            )
            session.query(Person).filter(Person.id.in_(people_ids)).delete(
                synchronize_session=False
            )
        session.query(Job).filter(Job.id == job.id).delete()
        session.query(CompanyDomain).filter(CompanyDomain.id == domain.id).delete()
        session.query(Company).filter(Company.id == company.id).delete()
        session.query(User).filter(User.id == user.id).delete()
        session.commit()
        session.close()


def test_classify_role_priority() -> None:
    assert classify_role("Technical Recruiter") == RolePriority.role_recruiter
    assert classify_role("Talent Acquisition Partner") == RolePriority.recruiter
    assert classify_role("Engineering Manager") == RolePriority.engineering_manager
    assert classify_role("Director of Product") == RolePriority.hiring_manager


def test_research_persists_contacts_by_priority(people_ctx) -> None:
    session, user, company, job = people_ctx
    provider = MockPeopleProvider(
        people=[
            PersonHit(
                full_name="Riley Recruiter",
                title="Technical Recruiter",
                company_name=company.name,
                linkedin_url="https://www.linkedin.com/in/riley-recruiter",
                location="Remote",
            ),
            PersonHit(
                full_name="Morgan Manager",
                title="Engineering Manager",
                company_name=company.name,
                linkedin_url="https://www.linkedin.com/in/morgan-em",
            ),
            PersonHit(
                full_name="Sam Staff",
                title="Staff Engineer",
                company_name=company.name,
            ),
        ]
    )
    result = PeopleResearchService(session, user.id, people=provider).research_for_job(job.id)
    assert len(result.people) == 3
    assert result.people[0].relevance == RolePriority.role_recruiter
    assert result.people[0].name == "Riley Recruiter"
    assert result.people[0].location == "Remote"
    assert result.people[0].provider == "mock-people"
    assert result.people[0].contact_id is not None

    contacts = (
        session.query(Contact).filter(Contact.user_id == user.id, Contact.company_id == company.id).all()
    )
    assert len(contacts) == 3
    sources = session.query(ContactSource).filter(ContactSource.user_id == user.id).all()
    assert len(sources) >= 3
    assert all(s.metadata_json.get("confidence") is not None for s in sources)


def test_never_invents_email_without_finder(people_ctx) -> None:
    session, user, company, job = people_ctx
    provider = MockPeopleProvider(
        people=[
            PersonHit(
                full_name="No Email Person",
                title="Recruiter",
                company_name=company.name,
            )
        ]
    )
    result = PeopleResearchService(
        session, user.id, people=provider, enrich_emails=True
    ).research_for_job(job.id)
    assert result.people[0].email is None
    assert result.people[0].email_verified is False
    assert session.query(EmailVerification).filter(EmailVerification.user_id == user.id).count() == 0


def test_email_enrichment_requires_verifier_evidence(people_ctx) -> None:
    session, user, company, job = people_ctx
    provider = MockPeopleProvider(
        people=[
            PersonHit(
                full_name="Alex Mock",
                title="Recruiter",
                company_name=company.name,
            )
        ]
    )
    result = PeopleResearchService(
        session,
        user.id,
        people=provider,
        email_finder=MockEmailFinderProvider(
            candidates=[
                EmailCandidate(email="alex.mock@people-target.example", confidence=0.9, sources=["mock"])
            ]
        ),
        email_verifier=MockEmailVerifierProvider(status=ProviderEmailStatus.valid),
        enrich_emails=True,
    ).research_for_job(job.id)

    assert result.people[0].email == "alex.mock@people-target.example"
    assert result.people[0].email_verified is True
    row = session.query(EmailVerification).filter(EmailVerification.user_id == user.id).one()
    assert row.status == EmailVerificationStatus.verified
    assert row.verified_at is not None
    contact = session.query(Contact).filter(Contact.id == result.people[0].contact_id).one()
    assert contact.status == ContactStatus.verified


def test_unverified_email_not_marked_verified(people_ctx) -> None:
    session, user, company, job = people_ctx
    provider = MockPeopleProvider(
        people=[PersonHit(full_name="Casey Risk", title="Recruiter", company_name=company.name)]
    )
    result = PeopleResearchService(
        session,
        user.id,
        people=provider,
        email_finder=MockEmailFinderProvider(
            candidates=[EmailCandidate(email="casey@people-target.example", confidence=0.4)]
        ),
        email_verifier=MockEmailVerifierProvider(status=ProviderEmailStatus.unknown),
        enrich_emails=True,
    ).research_for_job(job.id)
    assert result.people[0].email == "casey@people-target.example"
    assert result.people[0].email_verified is False
    row = session.query(EmailVerification).filter(EmailVerification.user_id == user.id).one()
    assert row.status == EmailVerificationStatus.unknown
    assert row.verified_at is None


def test_apollo_and_hunter_require_keys() -> None:
    with pytest.raises(ProviderNotConfiguredError):
        ApolloPeopleProvider(api_key="")
    with pytest.raises(ProviderNotConfiguredError):
        HunterEmailFinderProvider(api_key="")
