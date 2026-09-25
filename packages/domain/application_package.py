"""Soft discard helpers for application packages (return to pile / dismiss)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.models.enums import (
    ApplicationStatus,
    HumanTaskStatus,
    JobMatchStatus,
    WorkflowRunStatus,
)
from database.models.schema import Application, HumanTask, JobMatch, WorkflowRun
from packages.domain.career_workflow import CareerWorkflowService
from packages.domain.exceptions import DomainError, NotFoundError


class PackageDiscardResult(BaseModel):
    application_id: uuid.UUID
    action: Literal["return_to_pile", "dismiss"]
    match_status: str
    application_status: str


class ApplicationPackageService:
    """Tenant-scoped soft discard for Approvals packages."""

    def __init__(self, session: Session, user_id: uuid.UUID) -> None:
        self._session = session
        self._user_id = user_id

    def return_to_pile(self, application_id: uuid.UUID) -> PackageDiscardResult:
        return self._discard(application_id, action="return_to_pile")

    def dismiss_package(self, application_id: uuid.UUID) -> PackageDiscardResult:
        return self._discard(application_id, action="dismiss")

    def _discard(
        self,
        application_id: uuid.UUID,
        *,
        action: Literal["return_to_pile", "dismiss"],
    ) -> PackageDiscardResult:
        app = (
            self._session.query(Application)
            .filter(
                Application.id == application_id,
                Application.user_id == self._user_id,
            )
            .one_or_none()
        )
        if app is None:
            raise NotFoundError("Application not found")
        if app.status == ApplicationStatus.submitted:
            raise DomainError("Cannot soft-discard a submitted application")

        match = (
            self._session.query(JobMatch)
            .filter(
                JobMatch.user_id == self._user_id,
                JobMatch.job_id == app.job_id,
            )
            .order_by(JobMatch.created_at.desc())
            .first()
        )
        if match is None:
            raise NotFoundError("Job match not found for application")

        target_match = (
            JobMatchStatus.new if action == "return_to_pile" else JobMatchStatus.dismissed
        )
        match.status = target_match

        app.status = ApplicationStatus.withdrawn
        evidence: dict[str, Any] = {}
        if isinstance(app.submission_evidence, dict):
            evidence = dict(app.submission_evidence)
        evidence["soft_discard"] = {
            "action": action,
            "at": datetime.now(timezone.utc).isoformat(),
            "match_status": target_match.value,
        }
        app.submission_evidence = evidence

        self._close_human_tasks(application_id)
        self._cancel_pipeline_runs(application_id=application_id, job_match_id=match.id)

        self._session.commit()
        return PackageDiscardResult(
            application_id=application_id,
            action=action,
            match_status=target_match.value,
            application_status=app.status.value,
        )

    def _close_human_tasks(self, application_id: uuid.UUID) -> None:
        rows = (
            self._session.query(HumanTask)
            .filter(
                HumanTask.user_id == self._user_id,
                HumanTask.application_id == application_id,
                HumanTask.status.in_(
                    [HumanTaskStatus.open, HumanTaskStatus.in_progress]
                ),
            )
            .all()
        )
        now = datetime.now(timezone.utc).isoformat()
        for task in rows:
            details = dict(task.details or {})
            details["resolution"] = {
                "soft_discard": True,
                "resolved_at": now,
            }
            task.details = details
            task.status = HumanTaskStatus.cancelled

    def _cancel_pipeline_runs(
        self,
        *,
        application_id: uuid.UUID,
        job_match_id: uuid.UUID,
    ) -> None:
        runs = (
            self._session.query(WorkflowRun)
            .filter(
                WorkflowRun.user_id == self._user_id,
                WorkflowRun.workflow_type == CareerWorkflowService.WORKFLOW_TYPE,
                WorkflowRun.status.in_(
                    [
                        WorkflowRunStatus.queued,
                        WorkflowRunStatus.running,
                        WorkflowRunStatus.cancelling,
                    ]
                ),
            )
            .all()
        )
        now = datetime.now(timezone.utc).isoformat()
        for run in runs:
            meta = run.metadata_json if isinstance(run.metadata_json, dict) else {}
            if meta.get("application_id") != str(application_id) and meta.get(
                "job_match_id"
            ) != str(job_match_id):
                continue
            run.status = WorkflowRunStatus.cancelled
            updated = dict(meta)
            updated["paused"] = False
            updated["current_step"] = "cancelled"
            updated["status_message"] = "Package soft-discarded"
            updated["cancelled_at"] = now
            run.metadata_json = updated
