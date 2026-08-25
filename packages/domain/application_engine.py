"""ApplicationEngine — application lifecycle state machine with audit events.

SUBMITTED only with explicit success evidence.
CAPTCHA / unknown Q / auth / unsupported form / ambiguous → REQUIRES_HUMAN.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.models.enums import ApplicationStatus
from database.models.schema import Application, ApplicationEvent
from packages.domain.exceptions import DomainError, NotFoundError


class EngineState(StrEnum):
    PREPARED = "PREPARED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    IN_PROGRESS = "IN_PROGRESS"
    REQUIRES_HUMAN = "REQUIRES_HUMAN"
    SUBMITTED = "SUBMITTED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


# Valid directed transitions.
VALID_TRANSITIONS: dict[EngineState, frozenset[EngineState]] = {
    EngineState.PREPARED: frozenset(
        {
            EngineState.AWAITING_APPROVAL,
            EngineState.BLOCKED,
            EngineState.FAILED,
        }
    ),
    EngineState.AWAITING_APPROVAL: frozenset(
        {
            EngineState.IN_PROGRESS,
            EngineState.BLOCKED,
            EngineState.FAILED,
            EngineState.PREPARED,  # user rejected / revise
        }
    ),
    EngineState.IN_PROGRESS: frozenset(
        {
            EngineState.REQUIRES_HUMAN,
            EngineState.SUBMITTED,
            EngineState.FAILED,
            EngineState.BLOCKED,
            EngineState.AWAITING_APPROVAL,
        }
    ),
    EngineState.REQUIRES_HUMAN: frozenset(
        {
            EngineState.IN_PROGRESS,
            EngineState.AWAITING_APPROVAL,
            EngineState.FAILED,
            EngineState.BLOCKED,
        }
    ),
    EngineState.FAILED: frozenset(
        {
            EngineState.PREPARED,
            EngineState.AWAITING_APPROVAL,
        }
    ),
    EngineState.BLOCKED: frozenset(
        {
            EngineState.PREPARED,
            EngineState.AWAITING_APPROVAL,
        }
    ),
    EngineState.SUBMITTED: frozenset(),  # terminal
}

HUMAN_REASONS = frozenset(
    {
        "captcha",
        "unknown_question",
        "authentication_required",
        "unsupported_form",
        "ambiguous",
        "anti_bot",
    }
)

# Map engine states onto existing ApplicationStatus where sensible.
_ENGINE_TO_APP_STATUS: dict[EngineState, ApplicationStatus] = {
    EngineState.PREPARED: ApplicationStatus.draft,
    EngineState.AWAITING_APPROVAL: ApplicationStatus.draft,
    EngineState.IN_PROGRESS: ApplicationStatus.in_progress,
    EngineState.REQUIRES_HUMAN: ApplicationStatus.in_progress,
    EngineState.SUBMITTED: ApplicationStatus.submitted,
    EngineState.FAILED: ApplicationStatus.withdrawn,
    EngineState.BLOCKED: ApplicationStatus.draft,
}


class TransitionResult(BaseModel):
    application_id: uuid.UUID
    from_state: EngineState
    to_state: EngineState
    event_id: uuid.UUID
    evidence: dict[str, Any] = Field(default_factory=dict)


class ApplicationEngine:
    """Persistable state machine; every transition writes ApplicationEvent."""

    def __init__(self, session: Session, user_id: uuid.UUID) -> None:
        self._session = session
        self._user_id = user_id

    def get_state(self, application_id: uuid.UUID) -> EngineState:
        app = self._get_app(application_id)
        return self._read_engine_state(app)

    def can_transition(self, current: EngineState, target: EngineState) -> bool:
        return target in VALID_TRANSITIONS.get(current, frozenset())

    def transition(
        self,
        application_id: uuid.UUID,
        target: EngineState,
        *,
        reason: str | None = None,
        evidence: dict[str, Any] | None = None,
        actor: str = "system",
    ) -> TransitionResult:
        app = self._get_app(application_id)
        current = self._read_engine_state(app)
        if not self.can_transition(current, target):
            raise DomainError(
                f"Invalid transition {current.value} → {target.value}"
            )

        evidence = dict(evidence or {})

        if target == EngineState.SUBMITTED:
            if not _has_submission_evidence(evidence):
                raise DomainError(
                    "SUBMITTED requires explicit success evidence "
                    "(confirmation_id, confirmation_url, screenshot, or portal_application_id)"
                )

        if target == EngineState.REQUIRES_HUMAN:
            human_reason = (reason or evidence.get("human_reason") or "").lower()
            if human_reason and human_reason not in HUMAN_REASONS:
                # Still allow, but normalize unknown into ambiguous.
                evidence.setdefault("human_reason", "ambiguous")
                evidence["original_reason"] = human_reason
            elif human_reason:
                evidence["human_reason"] = human_reason
            elif "human_reason" not in evidence:
                evidence["human_reason"] = reason or "ambiguous"

        self._write_engine_state(app, target, evidence=evidence)
        app.status = _ENGINE_TO_APP_STATUS[target]
        if target == EngineState.SUBMITTED:
            app.applied_at = datetime.now(timezone.utc)
            app.submission_evidence = {
                **(app.submission_evidence or {}),
                **evidence,
                "engine_status": target.value,
            }

        event = ApplicationEvent(
            id=uuid.uuid4(),
            user_id=self._user_id,
            application_id=app.id,
            event_type=f"engine_transition:{current.value}->{target.value}",
            payload={
                "from_state": current.value,
                "to_state": target.value,
                "reason": reason,
                "evidence": evidence,
                "actor": actor,
                "at": datetime.now(timezone.utc).isoformat(),
            },
        )
        self._session.add(event)
        self._session.commit()
        self._session.refresh(event)
        return TransitionResult(
            application_id=app.id,
            from_state=current,
            to_state=target,
            event_id=event.id,
            evidence=evidence,
        )

    def mark_requires_human(
        self,
        application_id: uuid.UUID,
        *,
        human_reason: str,
        evidence: dict[str, Any] | None = None,
    ) -> TransitionResult:
        """Convenience for CAPTCHA / unknown Q / auth / unsupported / ambiguous."""
        reason = human_reason.lower().strip()
        if reason not in HUMAN_REASONS:
            reason = "ambiguous"
        return self.transition(
            application_id,
            EngineState.REQUIRES_HUMAN,
            reason=reason,
            evidence={**(evidence or {}), "human_reason": reason},
        )

    def _get_app(self, application_id: uuid.UUID) -> Application:
        app = (
            self._session.query(Application)
            .filter(Application.id == application_id, Application.user_id == self._user_id)
            .one_or_none()
        )
        if app is None:
            raise NotFoundError("Application not found")
        return app

    def _read_engine_state(self, app: Application) -> EngineState:
        evidence = app.submission_evidence if isinstance(app.submission_evidence, dict) else {}
        raw = evidence.get("engine_status")
        if raw:
            try:
                return EngineState(str(raw))
            except ValueError:
                pass
        # Derive from ApplicationStatus for legacy rows.
        if app.status == ApplicationStatus.submitted:
            return EngineState.SUBMITTED
        if app.status == ApplicationStatus.in_progress:
            return EngineState.IN_PROGRESS
        return EngineState.PREPARED

    def _write_engine_state(
        self,
        app: Application,
        state: EngineState,
        *,
        evidence: dict[str, Any],
    ) -> None:
        current = app.submission_evidence if isinstance(app.submission_evidence, dict) else {}
        merged = {**current, **evidence, "engine_status": state.value}
        app.submission_evidence = merged


def _has_submission_evidence(evidence: dict[str, Any]) -> bool:
    keys = (
        "confirmation_id",
        "confirmation_url",
        "screenshot",
        "screenshot_path",
        "portal_application_id",
        "confirmation_email_id",
    )
    for key in keys:
        value = evidence.get(key)
        if isinstance(value, str) and value.strip():
            return True
        if value is True:
            return True
    return evidence.get("success") is True and bool(evidence.get("proof"))
