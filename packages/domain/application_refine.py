"""Refine application draft materials via LLM (restyle only — never invent facts)."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.models.schema import Application
from packages.domain.exceptions import DomainError, NotFoundError
from packages.providers.llm.base import LLMMessage, LLMProvider, LLMRequest


class ApplicationRefineInput(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)


class ApplicationRefineResult(BaseModel):
    application_id: uuid.UUID
    cover_letter: str | None = None
    content: str | None = None
    prompt: str


_SYSTEM = (
    "You rewrite job-application draft text for style and tone only. "
    "Do not invent employers, dates, skills, metrics, titles, or achievements. "
    "Do not invent email addresses. "
    "Keep claims limited to what appears in the current draft. "
    "Return plain text for the rewritten cover letter / application materials."
)


class ApplicationRefineService:
    def __init__(
        self,
        session: Session,
        user_id: uuid.UUID,
        *,
        llm: LLMProvider,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._llm = llm

    def refine(
        self, application_id: uuid.UUID, payload: ApplicationRefineInput
    ) -> ApplicationRefineResult:
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

        evidence = (
            dict(app.submission_evidence)
            if isinstance(app.submission_evidence, dict)
            else {}
        )
        materials = (
            dict(evidence.get("draft_materials") or {})
            if isinstance(evidence.get("draft_materials"), dict)
            else {}
        )
        current_cover = materials.get("cover_letter") or materials.get("content") or ""
        if not str(current_cover).strip():
            current_cover = (
                "Draft application materials are not ready yet. "
                "Rewrite nothing factual; produce a short professional placeholder "
                "that asks the candidate to finalize details from their resume."
            )

        prompt = payload.prompt.strip()
        if not prompt:
            raise DomainError("Prompt is required")

        response = self._llm.complete(
            LLMRequest(
                messages=[
                    LLMMessage(role="system", content=_SYSTEM),
                    LLMMessage(
                        role="user",
                        content=(
                            f"User style instruction:\n{prompt}\n\n"
                            f"Current draft:\n{current_cover}\n\n"
                            "Rewrite the draft per the instruction."
                        ),
                    ),
                ],
                temperature=0.4,
                max_tokens=2000,
            )
        )
        rewritten = (response.content or "").strip()
        if not rewritten:
            raise DomainError("LLM returned empty rewrite")

        materials["cover_letter"] = rewritten
        materials["content"] = rewritten
        materials["last_refine_prompt"] = prompt
        evidence["draft_materials"] = materials
        if "engine_status" not in evidence:
            evidence["engine_status"] = "AWAITING_APPROVAL"
        app.submission_evidence = evidence
        self._session.commit()

        return ApplicationRefineResult(
            application_id=app.id,
            cover_letter=rewritten,
            content=rewritten,
            prompt=prompt,
        )
