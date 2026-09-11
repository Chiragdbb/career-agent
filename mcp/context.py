"""MCP auth and session helpers.

MCP uses the same tenant isolation as the web app. Identity is resolved from:

1. `MCP_USER_ID` — local users.id UUID (preferred for local/CI), or
2. `MCP_AUTH_SUBJECT` — Supabase auth subject mapped via UserService, or
3. Bearer-style `MCP_AUTH_TOKEN` treated as auth_subject when subject/id unset.

Never bypass approval / audit rules in tool handlers — call domain services only.
"""

from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.orm import Session

from packages.domain.exceptions import AuthenticationError
from packages.domain.users import UserService
from packages.shared.env import load_project_env
from packages.shared.security import InMemoryRateLimiter

_rate_limiter = InMemoryRateLimiter(max_requests=120, window_seconds=60)


def _session_factory() -> Session:
    from app.database import get_session_factory, init_db

    load_project_env()
    init_db()
    return get_session_factory()()


@contextmanager
def mcp_session() -> Iterator[Session]:
    session = _session_factory()
    try:
        yield session
    finally:
        session.close()


def resolve_mcp_user_id(session: Session) -> uuid.UUID:
    load_project_env()
    token = (os.getenv("MCP_AUTH_TOKEN") or "").strip()
    if token and not _rate_limiter.allow(f"mcp:{token[:16]}"):
        raise AuthenticationError("MCP rate limit exceeded")

    user_id_raw = (os.getenv("MCP_USER_ID") or "").strip()
    if user_id_raw:
        user = UserService(session).get_by_id(uuid.UUID(user_id_raw))
        if user is None:
            raise AuthenticationError("MCP_USER_ID does not match a local user")
        return user.id

    subject = (os.getenv("MCP_AUTH_SUBJECT") or token or "").strip()
    if not subject:
        raise AuthenticationError(
            "MCP authentication required: set MCP_USER_ID, MCP_AUTH_SUBJECT, or MCP_AUTH_TOKEN"
        )
    return UserService(session).get_or_create_by_auth_subject(subject).id
