"""Tenant isolation: user A must not access user B's owned resources."""

from __future__ import annotations

import uuid

import pytest

from database.models.enums import (
    ApplicationStatus,
    CompanyStatus,
    ContactStatus,
    JobMatchStatus,
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
    JobMatch,
    Outreach,
    Person,
    Resume,
    ResumeVersion,
    User,
)


def _seed_user_b_resources(session) -> dict[str, uuid.UUID]:
    """Create user B plus one owned row of each tenant-scoped resource type."""
    user_a = (
        session.query(User)
        .filter(User.auth_subject == "supabase-user-a")
        .one_or_none()
    )
    if user_a is None:
        user_a = User(
            id=uuid.uuid4(),
            auth_subject="supabase-user-a",
            status=UserStatus.active,
        )
        session.add(user_a)
        session.flush()

    existing_b = (
        session.query(User)
        .filter(User.auth_subject == "supabase-user-b")
        .one_or_none()
    )
    if existing_b is not None:
        session.query(Outreach).filter(Outreach.user_id == existing_b.id).delete()
        session.query(Application).filter(Application.user_id == existing_b.id).delete()
        session.query(Contact).filter(Contact.user_id == existing_b.id).delete()
        session.query(JobMatch).filter(JobMatch.user_id == existing_b.id).delete()
        session.query(ResumeVersion).filter(ResumeVersion.user_id == existing_b.id).delete()
        session.query(Resume).filter(Resume.user_id == existing_b.id).delete()
        session.delete(existing_b)
        session.flush()

    user_b = User(
        id=uuid.uuid4(),
        auth_subject="supabase-user-b",
        status=UserStatus.active,
    )
    session.add(user_b)
    session.flush()

    company = Company(id=uuid.uuid4(), name="Acme Isolation Co", status=CompanyStatus.active)
    person = Person(id=uuid.uuid4(), name="Recruiter B", status=PeopleStatus.active)
    session.add_all([company, person])
    session.flush()

    job = Job(
        id=uuid.uuid4(),
        company_id=company.id,
        title="Isolation Engineer",
        status=JobStatus.active,
        url=f"https://example.test/jobs/{uuid.uuid4()}",
    )
    session.add(job)
    session.flush()

    resume = Resume(
        id=uuid.uuid4(),
        user_id=user_b.id,
        name="User B Resume",
        status=ResumeStatus.active,
    )
    session.add(resume)
    session.flush()

    resume_version = ResumeVersion(
        id=uuid.uuid4(),
        resume_id=resume.id,
        user_id=user_b.id,
        status=ResumeVersionStatus.finalized,
        plain_text="experience",
    )
    session.add(resume_version)
    session.flush()

    job_match = JobMatch(
        id=uuid.uuid4(),
        user_id=user_b.id,
        job_id=job.id,
        status=JobMatchStatus.saved,
        score=0.9,
    )
    application = Application(
        id=uuid.uuid4(),
        user_id=user_b.id,
        job_id=job.id,
        resume_version_id=resume_version.id,
        status=ApplicationStatus.draft,
    )
    contact = Contact(
        id=uuid.uuid4(),
        user_id=user_b.id,
        people_id=person.id,
        company_id=company.id,
        name="Recruiter B",
        status=ContactStatus.identified,
    )
    session.add_all([job_match, application, contact])
    session.flush()

    outreach = Outreach(
        id=uuid.uuid4(),
        user_id=user_b.id,
        contact_id=contact.id,
        status=OutreachStatus.draft,
        subject="Hello from B",
        body="Confidential outreach",
    )
    session.add(outreach)
    session.commit()

    return {
        "job": job_match.id,
        "application": application.id,
        "resume": resume.id,
        "contact": contact.id,
        "outreach": outreach.id,
        "user_b": user_b.id,
    }


@pytest.fixture
def user_b_resources(auth_client):
    from app.database import get_session_factory

    me = auth_client.get(
        "/api/v1/me",
        headers={"Authorization": "Bearer token-user-a"},
    )
    assert me.status_code == 200

    session = get_session_factory()()
    try:
        ids = _seed_user_b_resources(session)
        yield ids
    finally:
        session.close()


@pytest.mark.parametrize(
    ("path_template", "id_key"),
    [
        ("/api/v1/jobs/{id}", "job"),
        ("/api/v1/applications/{id}", "application"),
        ("/api/v1/resumes/{id}", "resume"),
        ("/api/v1/contacts/{id}", "contact"),
        ("/api/v1/outreach/{id}", "outreach"),
    ],
)
def test_user_a_cannot_access_user_b_resources(
    auth_client, user_b_resources, path_template: str, id_key: str
) -> None:
    resource_id = user_b_resources[id_key]
    response = auth_client.get(
        path_template.format(id=resource_id),
        headers={"Authorization": "Bearer token-user-a"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_user_b_can_access_own_resources(auth_client, user_b_resources) -> None:
    for path_template, id_key in [
        ("/api/v1/jobs/{id}", "job"),
        ("/api/v1/applications/{id}", "application"),
        ("/api/v1/resumes/{id}", "resume"),
        ("/api/v1/contacts/{id}", "contact"),
        ("/api/v1/outreach/{id}", "outreach"),
    ]:
        response = auth_client.get(
            path_template.format(id=user_b_resources[id_key]),
            headers={"Authorization": "Bearer token-user-b"},
        )
        assert response.status_code == 200, (id_key, response.json())
        assert response.json()["id"] == str(user_b_resources[id_key])


def test_lists_are_tenant_scoped(auth_client, user_b_resources) -> None:
    b_ids = {
        str(user_b_resources["job"]),
        str(user_b_resources["application"]),
        str(user_b_resources["resume"]),
        str(user_b_resources["contact"]),
        str(user_b_resources["outreach"]),
    }
    for path in (
        "/api/v1/jobs",
        "/api/v1/applications",
        "/api/v1/resumes",
        "/api/v1/contacts",
        "/api/v1/outreach",
    ):
        response = auth_client.get(
            path,
            headers={"Authorization": "Bearer token-user-a"},
        )
        assert response.status_code == 200
        ids = {item["id"] for item in response.json()}
        assert ids.isdisjoint(b_ids)
