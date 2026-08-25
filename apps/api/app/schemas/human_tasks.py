from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class HumanTaskResponse(BaseModel):
    id: UUID
    task_type: str
    title: str | None = None
    status: str
    details: dict[str, Any] = Field(default_factory=dict)
    application_id: UUID | None = None
    outreach_id: UUID | None = None
    workflow_run_id: UUID | None = None
    resolution: dict[str, Any] | None = None


class HumanTaskResolveRequest(BaseModel):
    resolution: dict[str, Any] = Field(default_factory=dict)
    resume_workflow: bool = True
    notes: str | None = None


class OutreachDetailResponse(BaseModel):
    id: UUID
    contact_id: UUID
    application_id: UUID | None = None
    status: str
    outreach_type: str | None = None
    channel: str | None = None
    subject: str | None = None
    body: str | None = None
    reason: str | None = None
    recipient_email: str | None = None
    delivery_state: str | None = None
    human_task_id: UUID | None = None


class OutreachDraftRequest(BaseModel):
    contact_id: UUID
    outreach_type: str
    subject: str
    body: str
    reason: str
    application_id: UUID | None = None
    job_id: UUID | None = None
    company_id: UUID | None = None
    recipient_email: str | None = None
    request_approval: bool = True


class MailboxStatusResponse(BaseModel):
    provider: str
    status: str
    email_address: str | None = None
    has_encrypted_token: bool = False
    error: str | None = None


class CareerWorkflowStartRequest(BaseModel):
    job_match_id: UUID
    permit_submit: bool = False
    resume_version_id: UUID | None = None
    force: bool = False


class CareerWorkflowResponse(BaseModel):
    workflow_run_id: UUID
    status: str
    paused: bool = False
    human_task_id: UUID | None = None
    application_id: UUID | None = None
    completed_steps: list[str] = Field(default_factory=list)
    current_step: str | None = None
    outputs: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
