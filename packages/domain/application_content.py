"""ApplicationContentService — versioned drafts that never invent candidate facts."""

from __future__ import annotations

import json
import uuid
from typing import Any

from packages.domain.exceptions import DomainError
from packages.domain.resume_models import StructuredResume
from packages.domain.resume_validation import validate_against_canonical
from packages.prompts.application_content import (
    ContentGenerationRecord,
    ContentPromptKind,
    get_prompt,
)
from packages.providers.llm import LLMMessage, LLMProvider, LLMRequest
from packages.providers.llm_adapters import parse_llm_json
from packages.providers.exceptions import ProviderValidationError
from pydantic import BaseModel, Field


class GeneratedContent(BaseModel):
    kind: ContentPromptKind
    body: str
    subject: str | None = None
    warnings: list[str] = Field(default_factory=list)
    prompt_version: str
    model_version: str | None = None
    record: ContentGenerationRecord


class ApplicationContentService:
    def __init__(self, llm: LLMProvider, *, model: str | None = None) -> None:
        self._llm = llm
        self._model = model

    def generate(
        self,
        kind: ContentPromptKind,
        *,
        structured_resume: StructuredResume,
        job: dict[str, Any] | None = None,
        company: dict[str, Any] | None = None,
        person: dict[str, Any] | None = None,
        question: str | None = None,
        user_id: uuid.UUID | None = None,
        job_id: uuid.UUID | None = None,
        company_id: uuid.UUID | None = None,
        person_id: uuid.UUID | None = None,
        resume_version_id: uuid.UUID | None = None,
    ) -> GeneratedContent:
        prompt = get_prompt(kind)
        payload = {
            "resume": structured_resume.model_dump(),
            "job": job or {},
            "company": company or {},
            "person": person or {},
            "question": question,
            "kind": kind.value,
        }
        response = self._llm.complete(
            LLMRequest(
                messages=[
                    LLMMessage(role="system", content=prompt.system_prompt),
                    LLMMessage(role="user", content=json.dumps(payload)),
                ],
                model=self._model,
                response_format="json",
                temperature=0.1,
            )
        )
        try:
            data = parse_llm_json(response.content)
        except ProviderValidationError as exc:
            raise DomainError(f"Invalid LLM output for {kind.value}") from exc

        body = str(data.get("body") or data.get("answer") or "").strip()
        if not body:
            raise DomainError(f"Empty content for {kind.value}")
        subject = data.get("subject")
        warnings = [str(w) for w in (data.get("warnings") or []) if w]

        # Reject fabricated claims: metrics/employers/skills not in canonical resume.
        self._reject_unsupported_claims(body, structured_resume)

        model_version = response.model or self._model or self._llm.metadata.name
        record = ContentGenerationRecord(
            kind=kind,
            prompt_version=prompt.version,
            model_version=model_version,
            user_id=str(user_id) if user_id else None,
            job_id=str(job_id) if job_id else None,
            company_id=str(company_id) if company_id else None,
            person_id=str(person_id) if person_id else None,
            resume_version_id=str(resume_version_id) if resume_version_id else None,
            body=body,
            warnings=warnings,
        )
        return GeneratedContent(
            kind=kind,
            body=body,
            subject=str(subject) if subject else None,
            warnings=warnings,
            prompt_version=prompt.version,
            model_version=model_version,
            record=record,
        )

    def _reject_unsupported_claims(self, body: str, resume: StructuredResume) -> None:
        # Reuse metric detection by checking a synthetic summary against canonical.
        probe = StructuredResume.model_validate(
            {
                **resume.model_dump(),
                "summary": body,
            }
        )
        issues = validate_against_canonical(resume, probe)
        # Only block metric fabrications and skill inventions in free text for content.
        blocked = [
            i
            for i in issues
            if i.field.startswith("summary") or i.field == "skills"
        ]
        if blocked:
            details = "; ".join(f"{i.detail}: {i.unsupported_value}" for i in blocked)
            raise DomainError(f"Unsupported claims rejected: {details}")
