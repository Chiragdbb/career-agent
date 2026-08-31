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
from packages.providers.storage import MockStorageProvider, StorageProvider
from packages.providers.supabase_storage import SupabaseStorageProvider

from app.tasks import CeleryDiscoveryTaskClient, DiscoveryTaskClient, InlineDiscoveryTaskClient

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


def get_storage_provider(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> StorageProvider:
    """Return StorageProvider (tests may set app.state.storage_provider).

    Uses Supabase Storage when URL + service role key are configured;
    otherwise falls back to an in-memory MockStorageProvider (local/tests).
    """
    existing = getattr(request.app.state, "storage_provider", None)
    if existing is not None:
        return existing

    if settings.supabase_url and settings.supabase_service_role_key:
        provider: StorageProvider = SupabaseStorageProvider(
            supabase_url=settings.supabase_url,
            service_role_key=settings.supabase_service_role_key,
        )
    else:
        provider = MockStorageProvider()

    request.app.state.storage_provider = provider
    return provider


def get_storage_bucket(settings: Settings = Depends(get_settings)) -> str:
    bucket = settings.supabase_storage_bucket
    if bucket:
        return bucket
    return "resumes"


def get_discovery_task_client(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> DiscoveryTaskClient:
    """Return task client (overridable in tests via app.state).

    In development, discovery runs inline so a Celery worker is not required.
    Production uses Celery for async execution.
    """
    existing = getattr(request.app.state, "discovery_task_client", None)
    if existing is not None:
        return existing
    if settings.app_env == "development":
        client: DiscoveryTaskClient = InlineDiscoveryTaskClient()
    else:
        client = CeleryDiscoveryTaskClient()
    request.app.state.discovery_task_client = client
    return client


SettingsDep = Annotated[Settings, Depends(get_settings)]
DbSessionDep = Annotated[Session, Depends(get_db)]
RedisDep = Annotated[Redis, Depends(get_redis)]
CorrelationIdDep = Annotated[str, Depends(get_correlation_id)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
CurrentUserIdDep = Annotated[UUID, Depends(get_current_user_id)]
JwtVerifierDep = Annotated[JwtVerifier, Depends(get_jwt_verifier)]
StorageProviderDep = Annotated[StorageProvider, Depends(get_storage_provider)]
StorageBucketDep = Annotated[str, Depends(get_storage_bucket)]
DiscoveryTaskClientDep = Annotated[DiscoveryTaskClient, Depends(get_discovery_task_client)]
