"""Authentication and first-login user provisioning tests."""

from __future__ import annotations

from app.auth.jwt import AuthClaims, StaticJwtVerifier
from database.models.schema import User
from packages.domain.users import UserService


def test_unauthenticated_request_rejected(auth_client) -> None:
    response = auth_client.get("/api/v1/me")
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "unauthorized"


def test_invalid_token_rejected(auth_client) -> None:
    response = auth_client.get(
        "/api/v1/me",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_first_login_creates_local_user(auth_client) -> None:
    from app.database import get_session_factory

    session = get_session_factory()()
    try:
        before = (
            session.query(User)
            .filter(User.auth_subject == "supabase-user-a")
            .one_or_none()
        )
        if before is not None:
            session.delete(before)
            session.commit()
    finally:
        session.close()

    response = auth_client.get(
        "/api/v1/me",
        headers={"Authorization": "Bearer token-user-a"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["auth_subject"] == "supabase-user-a"
    assert body["status"] == "active"
    assert body["id"]

    # Second call reuses the same local user (idempotent).
    again = auth_client.get(
        "/api/v1/me",
        headers={"Authorization": "Bearer token-user-a"},
    )
    assert again.status_code == 200
    assert again.json()["id"] == body["id"]


def test_user_service_get_or_create(auth_client) -> None:
    # Ensure DB/session factory is initialized via app lifespan.
    from app.database import get_session_factory

    session = get_session_factory()()
    try:
        service = UserService(session)
        user = service.get_or_create_by_auth_subject("supabase-subject-unique-xyz")
        assert user.auth_subject == "supabase-subject-unique-xyz"
        again = service.get_or_create_by_auth_subject("supabase-subject-unique-xyz")
        assert again.id == user.id
        session.delete(user)
        session.commit()
    finally:
        session.close()


def test_static_verifier_registers_claims() -> None:
    verifier = StaticJwtVerifier()
    verifier.register("abc", AuthClaims(subject="sub-1", email="a@example.com"))
    claims = verifier.verify("abc")
    assert claims.subject == "sub-1"
    assert claims.email == "a@example.com"
