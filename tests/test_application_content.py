"""STEP 20 — ApplicationContentService with versioned prompts."""

from __future__ import annotations

import json
import uuid

import pytest

from packages.domain.application_content import ApplicationContentService
from packages.domain.exceptions import DomainError
from packages.domain.resume_models import ContactInfo, ExperienceEntry, StructuredResume
from packages.prompts.application_content import ContentPromptKind, get_prompt
from packages.providers.llm import MockLLMProvider


def _resume() -> StructuredResume:
    return StructuredResume(
        contact=ContactInfo(full_name="Pat Candidate"),
        summary="Backend engineer with Python experience.",
        skills=["Python", "Postgres"],
        experience=[
            ExperienceEntry(
                company="PastCo",
                title="Software Engineer",
                start_date="2020",
                end_date="2023",
                bullets=["Built APIs in Python"],
            )
        ],
    )


def test_prompt_registry_versions() -> None:
    for kind in ContentPromptKind:
        spec = get_prompt(kind)
        assert spec.version
        assert "Never invent" in spec.system_prompt or "never invent" in spec.system_prompt.lower() or "Do not invent" in spec.system_prompt or "only" in spec.system_prompt.lower()


def test_generate_records_versions() -> None:
    payload = json.dumps(
        {
            "body": "I am excited about the Python role given my PastCo API work.",
            "subject": "Application",
            "warnings": [],
        }
    )
    service = ApplicationContentService(MockLLMProvider(content=payload), model="mock-model")
    result = service.generate(
        ContentPromptKind.cover_letter,
        structured_resume=_resume(),
        job={"title": "Python Engineer"},
        user_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        resume_version_id=uuid.uuid4(),
    )
    assert result.prompt_version == "cover_letter-v1"
    assert result.model_version
    assert result.record.resume_version_id
    assert "PastCo" in result.body


def test_rejects_unsupported_metric_claims() -> None:
    payload = json.dumps(
        {
            "body": "I grew revenue by 500% and scaled to 50 million users at PastCo.",
            "warnings": [],
        }
    )
    service = ApplicationContentService(MockLLMProvider(content=payload))
    with pytest.raises(DomainError, match="Unsupported claims"):
        service.generate(
            ContentPromptKind.why_role,
            structured_resume=_resume(),
            job={"title": "Engineer"},
        )
