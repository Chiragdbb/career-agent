from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "apps" / "api"

# REPO_ROOT enables `import packages.providers` and `import database`.
# API_ROOT enables `import app`.
for path in (str(REPO_ROOT), str(API_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def static_jwt_verifier():
    from app.auth.jwt import AuthClaims, StaticJwtVerifier

    verifier = StaticJwtVerifier(
        {
            "token-user-a": AuthClaims(subject="supabase-user-a"),
            "token-user-b": AuthClaims(subject="supabase-user-b"),
        }
    )
    return verifier


@pytest.fixture
def auth_client(static_jwt_verifier):
    """API test client with mocked JWT verifier (no real Supabase calls)."""
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.dependencies import get_storage_provider
    from app.main import create_app
    from app.redis import get_redis
    from app.tasks import InlineDiscoveryTaskClient
    from packages.providers.storage import MockStorageProvider

    class FakeRedis:
        def __init__(self) -> None:
            self._store: dict[str, str] = {}

        def set(self, name: str, value: str, nx: bool = False, ex: int | None = None) -> bool:
            if nx and name in self._store:
                return False
            self._store[name] = value
            return True

        def get(self, name: str) -> str | None:
            return self._store.get(name)

        def delete(self, name: str) -> int:
            if name in self._store:
                del self._store[name]
                return 1
            return 0

        def setex(self, name: str, time: int, value: str) -> None:
            self._store[name] = value

        def publish(self, channel: str, message: str) -> int:
            return 0

        def pubsub(self, **kwargs):
            class _PubSub:
                def subscribe(self, *args, **kwargs): ...
                def listen(self): return iter(())
                def unsubscribe(self, *args, **kwargs): ...
                def close(self): ...

            return _PubSub()

    settings = get_settings()
    app = create_app(settings)
    app.state.jwt_verifier = static_jwt_verifier
    app.state.discovery_task_client = InlineDiscoveryTaskClient()
    storage = MockStorageProvider()
    app.state.storage_provider = storage
    fake_redis = FakeRedis()
    app.dependency_overrides[get_storage_provider] = lambda: storage
    app.dependency_overrides[get_redis] = lambda: fake_redis

    with TestClient(app) as client:
        client.mock_storage = storage  # type: ignore[attr-defined]
        yield client

    app.dependency_overrides.clear()


def seed_user_b_resources(session):
    """Create user B plus one owned row of each tenant-scoped resource type."""
    import uuid

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
        ids = seed_user_b_resources(session)
        yield ids
    finally:
        session.close()
