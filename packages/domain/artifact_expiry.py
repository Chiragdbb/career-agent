"""Expire unsent application package artifacts (72h / 24h after applied)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from database.models.enums import ApplicationStatus, OutreachStatus, ResumeVersionStatus
from database.models.schema import Application, Outreach, ResumeVersion


@dataclass
class ExpiryStats:
    applications_cleared: int = 0
    outreach_cancelled: int = 0
    resume_versions_discarded: int = 0


class ArtifactExpiryService:
    """Purge unsent package drafts; never delete sent outreach."""

    def __init__(self, session: Session, *, now: datetime | None = None) -> None:
        self._session = session
        self._now = now or datetime.now(timezone.utc)

    def expire_due(self, *, limit: int = 200) -> ExpiryStats:
        stats = ExpiryStats()
        rows = (
            self._session.query(Application)
            .order_by(Application.updated_at.asc())
            .limit(limit)
            .all()
        )
        for app in rows:
            if self._should_expire(app):
                cleared = self._clear_application(app)
                if cleared:
                    stats.applications_cleared += 1
                    stats.outreach_cancelled += self._cancel_unsent_outreach(app)
                    stats.resume_versions_discarded += self._discard_draft_resumes(app)
        self._session.commit()
        return stats

    def _should_expire(self, app: Application) -> bool:
        evidence = (
            app.submission_evidence if isinstance(app.submission_evidence, dict) else {}
        )
        materials = evidence.get("draft_materials")
        if not isinstance(materials, dict) or not materials:
            return False
        if materials.get("expired") is True:
            return False

        expires_at = self._parse_dt(materials.get("expires_at"))
        if expires_at is not None and expires_at <= self._now:
            return True

        created = app.created_at
        if created is not None:
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created + timedelta(hours=72) <= self._now:
                return True

        applied = app.applied_at
        if applied is not None:
            if applied.tzinfo is None:
                applied = applied.replace(tzinfo=timezone.utc)
            if applied + timedelta(hours=24) <= self._now:
                return True

        if app.status == ApplicationStatus.submitted:
            updated = app.updated_at or app.created_at
            if updated is not None:
                if updated.tzinfo is None:
                    updated = updated.replace(tzinfo=timezone.utc)
                if updated + timedelta(hours=24) <= self._now:
                    return True
        return False

    def _clear_application(self, app: Application) -> bool:
        evidence = (
            dict(app.submission_evidence)
            if isinstance(app.submission_evidence, dict)
            else {}
        )
        materials = evidence.get("draft_materials")
        if not isinstance(materials, dict):
            return False
        materials = {
            **materials,
            "cover_letter": None,
            "content": None,
            "hook_subject": None,
            "hook_body": None,
            "strategy_summary": None,
            "expired": True,
            "expired_at": self._now.isoformat(),
        }
        evidence["draft_materials"] = materials
        app.submission_evidence = evidence
        return True

    def _cancel_unsent_outreach(self, app: Application) -> int:
        rows = (
            self._session.query(Outreach)
            .filter(
                Outreach.user_id == app.user_id,
                Outreach.application_id == app.id,
                Outreach.status.in_(
                    [
                        OutreachStatus.draft,
                        OutreachStatus.pending_approval,
                        OutreachStatus.approved,
                    ]
                ),
            )
            .all()
        )
        count = 0
        for row in rows:
            row.status = OutreachStatus.cancelled
            count += 1
        return count

    def _discard_draft_resumes(self, app: Application) -> int:
        evidence = (
            app.submission_evidence if isinstance(app.submission_evidence, dict) else {}
        )
        materials = evidence.get("draft_materials") if isinstance(evidence, dict) else {}
        version_id = None
        if isinstance(materials, dict):
            raw = materials.get("resume_version_id")
            if raw:
                try:
                    version_id = uuid.UUID(str(raw))
                except (TypeError, ValueError):
                    version_id = None
        if version_id is None:
            return 0
        version = (
            self._session.query(ResumeVersion)
            .filter(
                ResumeVersion.id == version_id,
                ResumeVersion.user_id == app.user_id,
            )
            .one_or_none()
        )
        if version is None:
            return 0
        if version.status == ResumeVersionStatus.draft:
            version.status = ResumeVersionStatus.superseded
            return 1
        return 0

    @staticmethod
    def _parse_dt(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        try:
            text = str(value).replace("Z", "+00:00")
            dt = datetime.fromisoformat(text)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return None
