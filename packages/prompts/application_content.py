"""Versioned application content prompts and generation with fact checks."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ContentPromptKind(StrEnum):
    cover_letter = "cover_letter"
    recruiter_outreach = "recruiter_outreach"
    referral_request = "referral_request"
    hiring_manager_message = "hiring_manager_message"
    why_company = "why_company"
    why_role = "why_role"
    application_question = "application_question"


# Bump when prompt text changes — recorded with every generation.
PROMPT_REGISTRY: dict[ContentPromptKind, tuple[str, str]] = {
    ContentPromptKind.cover_letter: (
        "cover_letter-v1",
        (
            "Draft a concise cover letter using ONLY provided resume and job facts. "
            "Never invent employers, titles, dates, projects, technologies, achievements, or metrics. "
            "If a claim cannot be supported, omit it and add a warning."
        ),
    ),
    ContentPromptKind.recruiter_outreach: (
        "recruiter_outreach-v1",
        (
            "Draft a short recruiter outreach message using only provided facts. "
            "Do not invent email addresses or candidate experience. Require user approval before send."
        ),
    ),
    ContentPromptKind.referral_request: (
        "referral_request-v1",
        (
            "Draft a polite referral request using only provided facts about the candidate and role. "
            "Never invent shared history or achievements."
        ),
    ),
    ContentPromptKind.hiring_manager_message: (
        "hiring_manager_message-v1",
        (
            "Draft a concise hiring-manager note using only resume/job/company facts provided. "
            "No fabricated metrics or unstated experience."
        ),
    ),
    ContentPromptKind.why_company: (
        "why_company-v1",
        (
            "Answer why-company using company research and resume facts only. "
            "Do not invent company claims or candidate motives unsupported by inputs."
        ),
    ),
    ContentPromptKind.why_role: (
        "why_role-v1",
        (
            "Answer why-role using job description and resume facts only. "
            "Never invent skills or experience."
        ),
    ),
    ContentPromptKind.application_question: (
        "application_question-v1",
        (
            "Answer the application question using only resume (and optional job) facts. "
            "Never invent experience, skills, dates, employers, achievements, or metrics."
        ),
    ),
}


class PromptSpec(BaseModel):
    kind: ContentPromptKind
    version: str
    system_prompt: str


def get_prompt(kind: ContentPromptKind) -> PromptSpec:
    version, text = PROMPT_REGISTRY[kind]
    return PromptSpec(kind=kind, version=version, system_prompt=text)


class ContentGenerationRecord(BaseModel):
    """Audit record for a generated artifact (not necessarily persisted)."""

    kind: ContentPromptKind
    prompt_version: str
    model_version: str | None = None
    user_id: str | None = None
    job_id: str | None = None
    company_id: str | None = None
    person_id: str | None = None
    resume_version_id: str | None = None
    body: str
    warnings: list[str] = Field(default_factory=list)
