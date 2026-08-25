"""Tests for NotificationService, FollowUpService, Interview/Offer, events."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from database.models.enums import (
    ApplicationStatus,
    CompanyStatus,
    ContactStatus,
    FollowUpStatus,
    JobStatus,
    NotificationStatus,
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
    FollowUp,
    Job,
    Notification,
    Outreach,
    Person,
    Resume,
    ResumeVersion,
    User,
)
from packages.domain.events import InMemoryEventBus, UserEventPublisher, UserEventType
from packages.domain.follow_ups import FollowUpScheduleInput, FollowUpService
from packages.domain.interviews import InterviewCreate, InterviewService, OfferCreate, OfferService
from packages.domain.notifications import (
    NotificationCreate,
    NotificationService,
    NotificationType,
)
from packages.domain.preferences import PreferenceSettings, PreferencesService
from packages.providers.email_sender import MockEmailSenderProvider
from packages.providers.notification import MockNotificationProvider


def _session():
    from app.database import get_session_factory

    return get_session_factory()()


def _ensure_user(session, subject: str = "supabase-user-a") -> User:
    user = session.query(User).filter(User.auth_subject == subject).one_or_none()
    if user is None:
        user = User(id=uuid.uuid4(), auth_subject=subject, status=UserStatus.active)
        session.add(user)
        session.commit()
    return user


def _seed_application(session, user: User) -> Application:
    company = Company(id=uuid.uuid4(), name="SaaS Co", status=CompanyStatus.active)
    session.add(company)
    session.flush()
    job = Job(
        id=uuid.uuid4(),
        company_id=company.id,
        title="Engineer",
        status=JobStatus.active,
        url=f"https://example.test/saas/{uuid.uuid4()}",
    )
    session.add(job)
    session.flush()
    resume = Resume(
        id=uuid.uuid4(),
        user_id=user.id,
        name="Master",
        status=ResumeStatus.active,
    )
    session.add(resume)
    session.flush()
    version = ResumeVersion(
        id=uuid.uuid4(),
        user_id=user.id,
        resume_id=resume.id,
        status=ResumeVersionStatus.finalized,
    )
    session.add(version)
    session.flush()
    app = Application(
        id=uuid.uuid4(),
        user_id=user.id,
        job_id=job.id,
        status=ApplicationStatus.submitted,
        resume_version_id=version.id,
        submission_evidence={"confirmation_id": "abc"},
    )
    session.add(app)
    session.commit()
    return app


def _seed_outreach(session, user: User, application: Application | None = None) -> Outreach:
    person = Person(id=uuid.uuid4(), name="Recruiter", status=PeopleStatus.active)
    session.add(person)
    session.flush()
    contact = Contact(
        id=uuid.uuid4(),
        user_id=user.id,
        people_id=person.id,
        status=ContactStatus.verified,
        name="Recruiter",
    )
    session.add(contact)
    session.flush()
    outreach = Outreach(
        id=uuid.uuid4(),
        user_id=user.id,
        contact_id=contact.id,
        application_id=application.id if application else None,
        status=OutreachStatus.sent,
        subject="Intro",
        body="Hello",
        channel="email",
    )
    session.add(outreach)
    session.commit()
    return outreach


def test_notification_dedupe_and_email(auth_client):
    session = _session()
    user = _ensure_user(session)
    PreferencesService(session, user.id).update(
        PreferenceSettings(
            email_notifications_enabled=True,
            notification_email="user@example.com",
        )
    )
    sender = MockEmailSenderProvider()
    svc = NotificationService(session, user.id, email_sender=sender)

    dedupe = f"task:{uuid.uuid4()}"
    first = svc.create(
        NotificationCreate(
            notification_type=NotificationType.human_action_required,
            title="Need approval",
            body="Approve outreach",
            dedupe_key=dedupe,
            send_email=True,
        )
    )
    second = svc.create(
        NotificationCreate(
            notification_type=NotificationType.human_action_required,
            title="Need approval again",
            body="dup",
            dedupe_key=dedupe,
            send_email=True,
        )
    )
    assert first.duplicated is False
    assert second.duplicated is True
    assert second.id == first.id
    assert len(sender.sent) == 1
    assert sender.sent[0].to == ["user@example.com"]

    unread = svc.list_notifications(status=NotificationStatus.unread)
    assert any(n.id == first.id for n in unread)
    svc.mark_read(first.id)
    unread_after = svc.list_notifications(status=NotificationStatus.unread)
    assert all(n.id != first.id for n in unread_after)


def test_notification_never_invents_email(auth_client):
    session = _session()
    user = _ensure_user(session)
    PreferencesService(session, user.id).update(
        PreferenceSettings(email_notifications_enabled=True, notification_email=None)
    )
    sender = MockEmailSenderProvider()
    svc = NotificationService(session, user.id, email_sender=sender)
    view = svc.create(
        NotificationCreate(
            notification_type=NotificationType.workflow_failure,
            title="Failed",
            send_email=True,
            dedupe_key=f"fail:{uuid.uuid4()}",
        )
    )
    assert view.email_sent is False
    assert sender.sent == []


def test_follow_up_schedule_cancel_and_due(auth_client):
    session = _session()
    user = _ensure_user(session)
    app = _seed_application(session, user)
    outreach = _seed_outreach(session, user, app)
    bus = InMemoryEventBus()
    events = UserEventPublisher(bus)
    notif_provider = MockNotificationProvider()
    svc = FollowUpService(
        session, user.id, notifications=notif_provider, events=events
    )

    scheduled = svc.schedule(
        FollowUpScheduleInput(
            outreach_id=outreach.id,
            application_id=app.id,
            days_after=3,
        )
    )
    assert scheduled.status == FollowUpStatus.scheduled.value
    again = svc.schedule(
        FollowUpScheduleInput(outreach_id=outreach.id, application_id=app.id, days_after=3)
    )
    assert again.id == scheduled.id  # dedupe

    # Force due
    row = session.query(FollowUp).filter(FollowUp.id == scheduled.id).one()
    row.next_action_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    session.commit()

    due = svc.process_due()
    assert len(due) == 1
    assert due[0].status == FollowUpStatus.pending_approval.value
    assert due[0].human_task_id is not None

    # Reply cancels
    outreach.status = OutreachStatus.replied
    session.commit()
    # New follow-up then cancel
    row2 = FollowUp(
        id=uuid.uuid4(),
        user_id=user.id,
        outreach_id=outreach.id,
        application_id=app.id,
        status=FollowUpStatus.scheduled,
        next_action_at=datetime.now(timezone.utc) + timedelta(days=1),
        dedupe_key=f"outreach:{outreach.id}:followup-2",
        subject="Again",
        body="Body",
    )
    session.add(row2)
    session.commit()
    cancelled = svc.cancel_if_response(outreach_id=outreach.id)
    assert cancelled >= 1
    remaining = (
        session.query(FollowUp)
        .filter(
            FollowUp.user_id == user.id,
            FollowUp.outreach_id == outreach.id,
            FollowUp.status.in_(
                [FollowUpStatus.scheduled, FollowUpStatus.pending_approval]
            ),
        )
        .count()
    )
    assert remaining == 0


def test_interview_and_offer_timeline(auth_client):
    session = _session()
    user = _ensure_user(session)
    app = _seed_application(session, user)
    bus = InMemoryEventBus()
    events = UserEventPublisher(bus)

    interview = InterviewService(session, user.id, events=events).create(
        InterviewCreate(
            application_id=app.id,
            title="Onsite",
            round=2,
            format="onsite",
            interviewer="Hiring Manager",
        )
    )
    assert interview.round == 2
    offer = OfferService(session, user.id, events=events).create(
        OfferCreate(
            application_id=app.id,
            compensation="180k",
            equity="0.1%",
            location="Remote",
        )
    )
    assert offer.compensation == "180k"

    from packages.domain.dashboard import DashboardService

    detail = DashboardService(session, user.id).get_application_detail(app.id)
    types = {e.event_type for e in detail.events}
    assert "interview_scheduled" in types
    assert "offer_received" in types
    assert len(detail.interviews) == 1
    assert len(detail.offers) == 1

    published_types = set()
    from packages.domain.events import UserEvent

    for _ch, msg in bus.published:
        published_types.add(UserEvent.model_validate_json(msg).type)
    assert UserEventType.interview_scheduled in published_types
    assert UserEventType.offer_updated in published_types


def test_events_publisher_tenant_channel():
    bus = InMemoryEventBus()
    pub = UserEventPublisher(bus)
    user_id = uuid.uuid4()
    other = uuid.uuid4()
    pub.publish(user_id, UserEventType.jobs_discovered, {"count": 1})
    assert len(bus.published) == 1
    channel, raw = bus.published[0]
    assert str(user_id) in channel
    assert str(other) not in channel
    event = pub.parse_message(raw)
    assert event.user_id == user_id
    assert event.type == UserEventType.jobs_discovered


def test_saas_api_endpoints(auth_client):
    session = _session()
    user = _ensure_user(session)
    app = _seed_application(session, user)
    headers = {"Authorization": "Bearer token-user-a"}

    summary = auth_client.get("/api/v1/dashboard/summary", headers=headers)
    assert summary.status_code == 200
    body = summary.json()
    assert body["applications_count"] >= 1

    analytics = auth_client.get("/api/v1/analytics/summary", headers=headers)
    assert analytics.status_code == 200

    docs = auth_client.get("/api/v1/documents", headers=headers)
    assert docs.status_code == 200

    # Create notification via service then list via API
    NotificationService(session, user.id).create(
        NotificationCreate(
            notification_type=NotificationType.high_priority_job,
            title="Hot job",
            dedupe_key=f"job:{uuid.uuid4()}",
            send_email=False,
        )
    )
    notifs = auth_client.get("/api/v1/notifications?status=unread", headers=headers)
    assert notifs.status_code == 200
    assert len(notifs.json()) >= 1

    created = auth_client.post(
        "/api/v1/interviews",
        headers=headers,
        json={
            "application_id": str(app.id),
            "title": "Screen",
            "round": 1,
            "format": "phone",
        },
    )
    assert created.status_code == 201

    offer = auth_client.post(
        "/api/v1/offers",
        headers=headers,
        json={
            "application_id": str(app.id),
            "compensation": "170k",
            "location": "NYC",
        },
    )
    assert offer.status_code == 201

    detail = auth_client.get(f"/api/v1/applications/{app.id}", headers=headers)
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["status"] == "submitted"
    assert len(payload["interviews"]) >= 1
    assert len(payload["offers"]) >= 1

    # Tenant isolation: user B cannot see user A application
    headers_b = {"Authorization": "Bearer token-user-b"}
    denied = auth_client.get(f"/api/v1/applications/{app.id}", headers=headers_b)
    assert denied.status_code in (403, 404)
