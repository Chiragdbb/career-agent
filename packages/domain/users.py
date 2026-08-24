"""User identity mapping (Supabase Auth subject → local users row)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from database.models.enums import UserStatus
from database.models.schema import User
from packages.domain.exceptions import AuthenticationError, AuthorizationError


class UserService:
    """Resolve or provision the local user for an authenticated auth subject."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_or_create_by_auth_subject(self, auth_subject: str) -> User:
        subject = (auth_subject or "").strip()
        if not subject:
            raise AuthenticationError("Missing auth subject")

        user = (
            self._session.query(User)
            .filter(User.auth_subject == subject)
            .one_or_none()
        )
        if user is None:
            user = User(
                id=uuid.uuid4(),
                auth_subject=subject,
                status=UserStatus.active,
            )
            self._session.add(user)
            self._session.commit()
            self._session.refresh(user)
            return user

        if user.status == UserStatus.suspended:
            raise AuthorizationError("User account is suspended")
        if user.status == UserStatus.deleted:
            raise AuthorizationError("User account is deleted")

        return user

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self._session.query(User).filter(User.id == user_id).one_or_none()
