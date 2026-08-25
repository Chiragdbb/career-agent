"""User profile read/update (tenant-scoped, one row per user)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from database.models.enums import UserProfileStatus
from database.models.schema import UserProfile


@dataclass(frozen=True)
class ProfileData:
    display_name: str | None = None
    headline: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    summary: str | None = None


class ProfileService:
    """Manage the canonical user profile for one tenant."""

    def __init__(self, session: Session, user_id: uuid.UUID) -> None:
        self._session = session
        self._user_id = user_id

    def get_or_create(self) -> UserProfile:
        row = (
            self._session.query(UserProfile)
            .filter(UserProfile.user_id == self._user_id)
            .one_or_none()
        )
        if row is None:
            row = UserProfile(
                id=uuid.uuid4(),
                user_id=self._user_id,
                status=UserProfileStatus.active,
            )
            self._session.add(row)
            self._session.commit()
            self._session.refresh(row)
        return row

    def update(self, data: ProfileData) -> UserProfile:
        row = self.get_or_create()
        row.display_name = _normalize_optional_text(data.display_name)
        row.headline = _normalize_optional_text(data.headline)
        row.location = _normalize_optional_text(data.location)
        row.linkedin_url = _normalize_optional_text(data.linkedin_url)
        row.summary = _normalize_optional_text(data.summary)
        self._session.commit()
        self._session.refresh(row)
        return row


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
