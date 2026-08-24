"""Tenant-scoped resource access for user-owned entities.

Shared reference rows (e.g. `jobs`) are not returned directly; user-facing
\"jobs\" are modeled as `job_matches` owned by `user_id`.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from database.models.schema import (
    Application,
    Contact,
    JobMatch,
    Outreach,
    Resume,
)
from packages.domain.exceptions import NotFoundError


class TenantResourceService:
    """Read user-owned resources with mandatory tenant scoping."""

    def __init__(self, session: Session, user_id: uuid.UUID) -> None:
        self._session = session
        self._user_id = user_id

    # --- jobs (job_matches) -------------------------------------------------

    def get_job(self, resource_id: uuid.UUID) -> JobMatch:
        row = (
            self._session.query(JobMatch)
            .filter(JobMatch.id == resource_id, JobMatch.user_id == self._user_id)
            .one_or_none()
        )
        if row is None:
            raise NotFoundError("Job not found")
        return row

    def list_jobs(self) -> list[JobMatch]:
        return (
            self._session.query(JobMatch)
            .filter(JobMatch.user_id == self._user_id)
            .order_by(JobMatch.created_at.desc())
            .all()
        )

    # --- applications -------------------------------------------------------

    def get_application(self, resource_id: uuid.UUID) -> Application:
        row = (
            self._session.query(Application)
            .filter(
                Application.id == resource_id,
                Application.user_id == self._user_id,
            )
            .one_or_none()
        )
        if row is None:
            raise NotFoundError("Application not found")
        return row

    def list_applications(self) -> list[Application]:
        return (
            self._session.query(Application)
            .filter(Application.user_id == self._user_id)
            .order_by(Application.created_at.desc())
            .all()
        )

    # --- resumes ------------------------------------------------------------

    def get_resume(self, resource_id: uuid.UUID) -> Resume:
        row = (
            self._session.query(Resume)
            .filter(Resume.id == resource_id, Resume.user_id == self._user_id)
            .one_or_none()
        )
        if row is None:
            raise NotFoundError("Resume not found")
        return row

    def list_resumes(self) -> list[Resume]:
        return (
            self._session.query(Resume)
            .filter(Resume.user_id == self._user_id)
            .order_by(Resume.created_at.desc())
            .all()
        )

    # --- contacts -----------------------------------------------------------

    def get_contact(self, resource_id: uuid.UUID) -> Contact:
        row = (
            self._session.query(Contact)
            .filter(Contact.id == resource_id, Contact.user_id == self._user_id)
            .one_or_none()
        )
        if row is None:
            raise NotFoundError("Contact not found")
        return row

    def list_contacts(self) -> list[Contact]:
        return (
            self._session.query(Contact)
            .filter(Contact.user_id == self._user_id)
            .order_by(Contact.created_at.desc())
            .all()
        )

    # --- outreach -----------------------------------------------------------

    def get_outreach(self, resource_id: uuid.UUID) -> Outreach:
        row = (
            self._session.query(Outreach)
            .filter(Outreach.id == resource_id, Outreach.user_id == self._user_id)
            .one_or_none()
        )
        if row is None:
            raise NotFoundError("Outreach not found")
        return row

    def list_outreach(self) -> list[Outreach]:
        return (
            self._session.query(Outreach)
            .filter(Outreach.user_id == self._user_id)
            .order_by(Outreach.created_at.desc())
            .all()
        )
