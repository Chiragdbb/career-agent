from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ScoreBreakdownResponse(BaseModel):
    total: float
    role: float
    location: float
    work_arrangement: float
    salary: float
    skills: float
    seniority: float
    notes: list[str] = Field(default_factory=list)


class JobMatchSummaryResponse(BaseModel):
    id: UUID
    job_id: UUID
    status: str
    score: float | None = None
    title: str
    company_name: str | None = None
    location: str | None = None
    work_arrangement: str | None = None
    url: str | None = None


class JobMatchDetailResponse(JobMatchSummaryResponse):
    description: str | None = None
    job_skills: list[str] = Field(default_factory=list)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    score_breakdown: ScoreBreakdownResponse | None = None
    explanation: str | None = None
    created_at: datetime | None = None


class DiscoverJobsRequest(BaseModel):
    max_results: int = Field(default=5, ge=1, le=20)
    idempotency_key: str | None = Field(default=None, max_length=128)


class DiscoverJobsResponse(BaseModel):
    workflow_run_id: UUID
    task_id: str
    status: str
    idempotency_key: str | None = None


class WorkflowRunResponse(BaseModel):
    id: UUID
    workflow_type: str
    status: str
    error: str | None = None
    metadata: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
