from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis import Redis
from sqlalchemy.orm import Session

from app.auth.jwt import AuthClaims, JwtVerifier, SupabaseJwksVerifier
from app.config import Settings, get_settings
from app.database import get_db
from app.redis import get_redis
from database.models.schema import User
from packages.domain.exceptions import AuthenticationError
from packages.domain.users import UserService

_bearer = HTTPBearer(auto_error=False)


def get_correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "unknown")


def get_jwt_verifier(request: Request, settings: Settings = Depends(get_settings)) -> JwtVerifier:
    """Return the app-configured JWT verifier (overridable in tests)."""
    existing = getattr(request.app.state, "jwt_verifier", None)
    if existing is not None:
        return existing
    if not settings.supabase_url:
        raise AuthenticationError("Supabase Auth is not configured")
    verifier = SupabaseJwksVerifier(settings.supabase_url)
    request.app.state.jwt_verifier = verifier
    return verifier


def get_current_user(
    session: Annotated[Session, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    verifier: Annotated[JwtVerifier, Depends(get_jwt_verifier)],
) -> User:
    """Verify the Bearer token and resolve (or create) the local user row."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Authentication required")

    claims: AuthClaims = verifier.verify(credentials.credentials)
    return UserService(session).get_or_create_by_auth_subject(claims.subject)


def get_current_user_id(user: Annotated[User, Depends(get_current_user)]) -> UUID:
    return user.id


SettingsDep = Annotated[Settings, Depends(get_settings)]
DbSessionDep = Annotated[Session, Depends(get_db)]
RedisDep = Annotated[Redis, Depends(get_redis)]
CorrelationIdDep = Annotated[str, Depends(get_correlation_id)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
CurrentUserIdDep = Annotated[UUID, Depends(get_current_user_id)]
JwtVerifierDep = Annotated[JwtVerifier, Depends(get_jwt_verifier)]
