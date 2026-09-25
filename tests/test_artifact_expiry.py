"""Tests for ArtifactExpiryService."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from database.models.enums import (
    ApplicationStatus,
    CompanyStatus,
    JobStatus,
    OutreachStatus,
    PeopleStatus,
    ResumeStatus,
    ResumeVersionStatus,
    UserStatus,
)
from database.models.schema import (
    Application,
    Company,
    Contact,
    Job,
    Outreach,
    Person,
    Resume,
    ResumeVersion,
    User,
)
from packages.domain.artifact_expiry import ArtifactExpiryService


def _session():
    from app.database import get_session_factory

    return get_session_factory()()


@pytest.fixture
def expiry_ctx():
    session = _session()
    user = User(id=uuid.uuid4(), auth_subject=f"exp-{uuid.uuid4()}", status=UserStatus.active)
    company = Company(id=uuid.uuid4(), name="Exp Co", status=CompanyStatus.active)
    session.add_all([user, company])
    session.commit()
    job = Job(
        id=uuid.uuid4(),
        company_id=company.id,
        title="Eng",
        status=JobStatus.active,
        url=f"https://example.com/{uuid.uuid4()}",
    )
    resume = Resume(id=uuid.uuid4(), user_id=user.id, name="M", status=ResumeStatus.active)
    session.add_all([job, resume])
    session.commit()
    version = ResumeVersion(
        id=uuid.uuid4(),
        resume_id=resume.id,
        user_id=user.id,
        status=ResumeVersionStatus.draft,
        plain_text="Python",
    )
    person = Person(id=uuid.uuid4(), name="Pat", status=PeopleStatus.active)
    session.add_all([version, person])
    session.commit()
    contact = Contact(
        id=uuid.uuid4(),
        user_id=user.id,
        people_id=person.id,
        company_id=company.id,
        name="Pat",
    )
    session.add(contact)
    session.commit()

    now = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)
    app = Application(
        id=uuid.uuid4(),
        user_id=user.id,
        job_id=job.id,
        status=ApplicationStatus.draft,
        resume_version_id=version.id,
        submission_evidence={
            "draft_materials": {
                "cover_letter": "Hi",
                "hook_subject": "Subj",
                "hook_body": "Body",
                "resume_version_id": str(version.id),
                "expires_at": (now - timedelta(hours=1)).isoformat(),
            }
        },
    )
    session.add(app)
    session.commit()
    outreach = Outreach(
        id=uuid.uuid4(),
        user_id=user.id,
        contact_id=contact.id,
        application_id=app.id,
        status=OutreachStatus.draft,
        subject="Subj",
        body="Body",
    )
    sent = Outreach(
        id=uuid.uuid4(),
        user_id=user.id,
        contact_id=contact.id,
        application_id=app.id,
        status=OutreachStatus.sent,
        subject="Sent",
        body="Keep me",
    )
    session.add_all([outreach, sent])
    session.commit()
    try:
        yield session, user, app, version, outreach, sent, now
    finally:
        session.query(Outreach).filter(Outreach.user_id == user.id).delete()
        session.query(Application).filter(Application.id == app.id).delete()
        session.query(Contact).filter(Contact.id == contact.id).delete()
        session.query(Person).filter(Person.id == person.id).delete()
        session.query(ResumeVersion).filter(ResumeVersion.id == version.id).delete()
        session.query(Resume).filter(Resume.id == resume.id).delete()
        session.query(Job).filter(Job.id == job.id).delete()
        session.query(Company).filter(Company.id == company.id).delete()
        session.query(User).filter(User.id == user.id).delete()
        session.commit()
        session.close()


def test_expires_unsent_materials_keeps_sent(expiry_ctx) -> None:
    session, user, app, version, outreach, sent, now = expiry_ctx
    ArtifactExpiryService(session, now=now).expire_due()
    session.refresh(app)
    session.refresh(outreach)
    session.refresh(sent)
    session.refresh(version)
    materials = (app.submission_evidence or {}).get("draft_materials") or {}
    assert materials.get("expired") is True
    assert materials.get("cover_letter") is None
    assert outreach.status == OutreachStatus.cancelled
    assert sent.status == OutreachStatus.sent
    assert version.status == ResumeVersionStatus.superseded


def test_fresh_package_not_expired(expiry_ctx) -> None:
    session, user, app, version, outreach, sent, now = expiry_ctx
    # Reset to fresh expiry window.
    app.submission_evidence = {
        "draft_materials": {
            "cover_letter": "Keep",
            "expires_at": (now + timedelta(hours=48)).isoformat(),
        }
    }
    session.commit()
    ArtifactExpiryService(session, now=now).expire_due()
    session.refresh(app)
    materials = (app.submission_evidence or {}).get("draft_materials") or {}
    assert materials.get("expired") is not True
    assert materials.get("cover_letter") == "Keep"
