from __future__ import annotations

from datetime import datetime
from typing import Literal
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
    is_new: bool = False


class JobMatchDetailResponse(JobMatchSummaryResponse):
    description: str | None = None
    job_skills: list[str] = Field(default_factory=list)
    matched_skills: list[str] = Field(default_factory=list)
    possible_matches: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    score_breakdown: ScoreBreakdownResponse | None = None
    explanation: str | None = None
    created_at: datetime | None = None
    company_domain: str | None = None
    source: str | None = None
    external_id: str | None = None
    employment_type: str | None = None
    remote_type: str | None = None
    seniority: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    requirements: list[str] = Field(default_factory=list)
    posted_at: datetime | None = None
    last_scraped_at: datetime | None = None
    scraped_at: datetime | None = None
    job_status: str | None = None


class DiscoverJobsRequest(BaseModel):
    max_results: int = Field(default=5, ge=1, le=20)
    idempotency_key: str | None = Field(default=None, max_length=128)


class DiscoverJobsResponse(BaseModel):
    workflow_run_id: UUID
    task_id: str
    status: str
    idempotency_key: str | None = None


class RescrapeJobResponse(BaseModel):
    workflow_run_id: UUID
    task_id: str
    status: str
    match_id: UUID


class WorkflowRunResponse(BaseModel):
    id: UUID
    workflow_type: str
    status: str
    error: str | None = None
    metadata: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    task_count: int = 0
    completed_task_count: int = 0
    failed_task_count: int = 0


class WorkflowTaskResponse(BaseModel):
    id: UUID
    workflow_run_id: UUID
    task_type: str
    status: str
    input_payload: dict | None = None
    output_payload: dict | None = None
    error: str | None = None
    attempt: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WorkflowProgressEventResponse(BaseModel):
    id: UUID
    step: str
    phase: str
    message: str
    display: dict | None = None
    created_at: datetime | None = None


class WorkflowProgressResponse(BaseModel):
    run: WorkflowRunResponse
    events: list[WorkflowProgressEventResponse] = Field(default_factory=list)
    eta_label: str


class JobMatchUpdateRequest(BaseModel):
    status: Literal["new", "reviewed", "saved", "dismissed", "applied"]


class JobBatchActionRequest(BaseModel):
    match_ids: list[UUID] = Field(min_length=1, max_length=50)
    action: Literal["save", "dismiss", "start_pipeline"]
