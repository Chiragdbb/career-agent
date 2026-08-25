"""API schemas for dashboard, notifications, follow-ups, interviews, offers."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DashboardSummaryResponse(BaseModel):
    jobs_count: int
    applications_count: int
    open_human_tasks: int
    unread_notifications: int
    upcoming_interviews: int
    pending_offers: int
    open_follow_ups: int
    contacts_count: int
    outreach_count: int
    documents_count: int


class ApplicationSummaryResponse(BaseModel):
    id: UUID
    job_id: UUID
    status: str
    job_title: str | None = None
    company_name: str | None = None
    applied_at: datetime | None = None


class ApplicationDetailResponse(BaseModel):
    id: UUID
    job_id: UUID
    status: str
    applied_at: datetime | None = None
    resume_version_id: UUID | None = None
    cover_letter_document_id: UUID | None = None
    submission_evidence: dict[str, Any] | None = None
    job_title: str | None = None
    company_name: str | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)
    documents: list[dict[str, Any]] = Field(default_factory=list)
    outreach: list[dict[str, Any]] = Field(default_factory=list)
    follow_ups: list[dict[str, Any]] = Field(default_factory=list)
    human_tasks: list[dict[str, Any]] = Field(default_factory=list)
    interviews: list[dict[str, Any]] = Field(default_factory=list)
    offers: list[dict[str, Any]] = Field(default_factory=list)


class DocumentResponse(BaseModel):
    id: str
    filename: str | None = None
    mime_type: str | None = None
    status: str
    application_id: str | None = None
    resume_version_id: str | None = None


class NotificationResponse(BaseModel):
    id: UUID
    notification_type: str | None = None
    title: str | None = None
    body: str | None = None
    status: str
    data: dict[str, Any] = Field(default_factory=dict)
    dedupe_key: str | None = None
    created_at: datetime | None = None
    email_sent: bool = False
    duplicated: bool = False


class FollowUpScheduleRequest(BaseModel):
    outreach_id: UUID | None = None
    application_id: UUID | None = None
    days_after: int | None = Field(default=None, ge=1, le=90)
    subject: str | None = None
    body: str | None = None
    reason: str = "Scheduled follow-up after outreach"
    dedupe_key: str | None = None


class FollowUpResponse(BaseModel):
    id: UUID
    status: str
    next_action_at: datetime
    application_id: UUID | None = None
    outreach_id: UUID | None = None
    subject: str | None = None
    body: str | None = None
    reason: str | None = None
    cancelled_reason: str | None = None
    dedupe_key: str
    human_task_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class InterviewCreateRequest(BaseModel):
    application_id: UUID
    title: str | None = None
    scheduled_at: datetime | None = None
    notes: str | None = None
    round: int | None = Field(default=None, ge=1, le=20)
    format: str | None = None
    interviewer: str | None = None
    status: str = "scheduled"


class InterviewUpdateRequest(BaseModel):
    title: str | None = None
    scheduled_at: datetime | None = None
    notes: str | None = None
    round: int | None = Field(default=None, ge=1, le=20)
    format: str | None = None
    interviewer: str | None = None
    status: str | None = None


class InterviewResponse(BaseModel):
    id: UUID
    application_id: UUID
    status: str
    title: str | None = None
    scheduled_at: datetime | None = None
    notes: str | None = None
    round: int | None = None
    format: str | None = None
    interviewer: str | None = None


class OfferCreateRequest(BaseModel):
    application_id: UUID
    compensation: str | None = None
    equity: str | None = None
    location: str | None = None
    deadline: datetime | None = None
    status: str = "pending"
    details: dict[str, Any] = Field(default_factory=dict)


class OfferUpdateRequest(BaseModel):
    compensation: str | None = None
    equity: str | None = None
    location: str | None = None
    deadline: datetime | None = None
    status: str | None = None
    details: dict[str, Any] | None = None


class OfferResponse(BaseModel):
    id: UUID
    application_id: UUID
    status: str
    offer_deadline: datetime | None = None
    compensation: str | None = None
    equity: str | None = None
    location: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class AnalyticsSummaryResponse(BaseModel):
    jobs_count: int
    applications_count: int
    contacts_count: int
    outreach_count: int
    interviews_count: int
    offers_count: int
    open_human_tasks: int
    unread_notifications: int
