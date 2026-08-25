"""STEP 25 — OutreachService tests."""

from __future__ import annotations

import uuid

import pytest

from database.models.enums import (
    ContactStatus,
    EmailVerificationStatus,
    PeopleStatus,
    UserStatus,
)
from database.models.schema import (
    Contact,
    EmailVerification,
    HumanTask,
    Outreach,
    OutreachEvent,
    Person,
    User,
)
from packages.domain.exceptions import DomainError
from packages.domain.outreach import OutreachDraftInput, OutreachService, OutreachType
from packages.providers.email_sender import MockEmailSenderProvider
from packages.providers.notification import MockNotificationProvider


def _session():
    from app.database import get_session_factory

    return get_session_factory()()


@pytest.fixture
def outreach_ctx():
    session = _session()
    user = User(id=uuid.uuid4(), auth_subject=f"out-{uuid.uuid4()}", status=UserStatus.active)
    person = Person(id=uuid.uuid4(), name="Recruiter R", status=PeopleStatus.active)
    session.add_all([user, person])
    session.commit()
    contact = Contact(
        id=uuid.uuid4(),
        user_id=user.id,
        people_id=person.id,
        status=ContactStatus.verified,
        name="Recruiter R",
        title="Recruiter",
    )
    session.add(contact)
    session.commit()
    ev = EmailVerification(
        id=uuid.uuid4(),
        user_id=user.id,
        contact_id=contact.id,
        email="recruiter@acme.example",
        status=EmailVerificationStatus.verified,
    )
    session.add(ev)
    session.commit()
    sender = MockEmailSenderProvider()
    notif = MockNotificationProvider()
    try:
        yield session, user, contact, sender, notif
    finally:
        session.query(HumanTask).filter(HumanTask.user_id == user.id).delete()
        session.query(OutreachEvent).filter(OutreachEvent.user_id == user.id).delete()
        session.query(Outreach).filter(Outreach.user_id == user.id).delete()
        session.query(EmailVerification).filter(EmailVerification.user_id == user.id).delete()
        session.query(Contact).filter(Contact.user_id == user.id).delete()
        session.query(Person).filter(Person.id == person.id).delete()
        session.query(User).filter(User.id == user.id).delete()
        session.commit()
        session.close()


def test_draft_requires_approval_and_does_not_send(outreach_ctx) -> None:
    session, user, contact, sender, notif = outreach_ctx
    svc = OutreachService(session, user.id, email_sender=sender, notifications=notif)
    view = svc.create_draft(
        OutreachDraftInput(
            contact_id=contact.id,
            outreach_type=OutreachType.recruiter,
            subject="Hello",
            body="Interested in the role.",
            reason="High match score",
            recipient_email="recruiter@acme.example",
        )
    )
    assert view.status == "pending_approval"
    assert view.delivery_state == "DRAFT"
    assert view.human_task_id is not None
    assert sender.sent == []


def test_approve_and_send(outreach_ctx) -> None:
    session, user, contact, sender, notif = outreach_ctx
    svc = OutreachService(session, user.id, email_sender=sender, notifications=notif)
    draft = svc.create_draft(
        OutreachDraftInput(
            contact_id=contact.id,
            outreach_type=OutreachType.referral,
            subject="Referral?",
            body="Could you refer me?",
            reason="Employee contact found",
            recipient_email="recruiter@acme.example",
        )
    )
    approved = svc.approve(draft.id)
    assert approved.status == "approved"
    assert approved.delivery_state == "APPROVED"
    sent = svc.send(draft.id)
    assert sent.status == "sent"
    assert sent.delivery_state == "SENT"
    assert len(sender.sent) == 1
    assert sender.sent[0].to == ["recruiter@acme.example"]


def test_cannot_invent_recipient_email(outreach_ctx) -> None:
    session, user, contact, sender, notif = outreach_ctx
    svc = OutreachService(session, user.id, email_sender=sender, notifications=notif)
    with pytest.raises(DomainError, match="never invented"):
        svc.create_draft(
            OutreachDraftInput(
                contact_id=contact.id,
                outreach_type=OutreachType.hiring_manager,
                subject="Hi",
                body="Hello",
                reason="HM outreach",
                recipient_email="invented@not-real.example",
            )
        )
