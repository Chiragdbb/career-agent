from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
    correlation_id: str | None = None


class HealthChecks(BaseModel):
    database: str
    redis: str


class HealthResponse(BaseModel):
    status: str = Field(description="overall | degraded | unhealthy")
    service: str
    checks: HealthChecks
    correlation_id: str | None = None


class MeResponse(BaseModel):
    id: UUID
    auth_subject: str
    status: str


class JobMatchResponse(BaseModel):
    id: UUID
    job_id: UUID
    status: str
    score: float | None = None


class ApplicationResponse(BaseModel):
    id: UUID
    job_id: UUID
    status: str


class ResumeResponse(BaseModel):
    id: UUID
    name: str
    status: str


class ContactResponse(BaseModel):
    id: UUID
    name: str | None = None
    status: str


class OutreachResponse(BaseModel):
    id: UUID
    contact_id: UUID
    status: str
    subject: str | None = None
