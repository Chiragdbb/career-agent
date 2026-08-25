from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.dependencies import CurrentUserIdDep, DbSessionDep, DiscoveryTaskClientDep
from app.schemas.jobs import (
    DiscoverJobsRequest,
    DiscoverJobsResponse,
    JobMatchDetailResponse,
    JobMatchSummaryResponse,
    ScoreBreakdownResponse,
    WorkflowRunResponse,
)
from packages.domain.jobs import DiscoveryTriggerService, JobListingService

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _listing(session: DbSessionDep, user_id: CurrentUserIdDep) -> JobListingService:
    return JobListingService(session, user_id)


def _to_summary(row) -> JobMatchSummaryResponse:
    return JobMatchSummaryResponse(
        id=row.id,
        job_id=row.job_id,
        status=row.status,
        score=row.score,
        title=row.title,
        company_name=row.company_name,
        location=row.location,
        work_arrangement=row.work_arrangement,
        url=row.url,
    )


def _to_detail(row) -> JobMatchDetailResponse:
    breakdown = None
    if row.score_breakdown is not None:
        breakdown = ScoreBreakdownResponse(
            total=row.score_breakdown.total,
            role=row.score_breakdown.role,
            location=row.score_breakdown.location,
            work_arrangement=row.score_breakdown.work_arrangement,
            salary=row.score_breakdown.salary,
            skills=row.score_breakdown.skills,
            seniority=row.score_breakdown.seniority,
            notes=list(row.score_breakdown.notes),
        )
    return JobMatchDetailResponse(
        id=row.id,
        job_id=row.job_id,
        status=row.status,
        score=row.score,
        title=row.title,
        company_name=row.company_name,
        location=row.location,
        work_arrangement=row.work_arrangement,
        url=row.url,
        description=row.description,
        job_skills=row.job_skills,
        matched_skills=row.matched_skills,
        missing_skills=row.missing_skills,
        score_breakdown=breakdown,
        explanation=row.explanation,
        created_at=row.created_at,
    )


@router.post("/discover", response_model=DiscoverJobsResponse, status_code=202)
def discover_jobs(
    body: DiscoverJobsRequest,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
    task_client: DiscoveryTaskClientDep,
) -> DiscoverJobsResponse:
    trigger = DiscoveryTriggerService(session, user_id)
    queued = trigger.enqueue(
        idempotency_key=body.idempotency_key,
        max_results=body.max_results,
    )
    task_id = task_client.enqueue_discover_jobs(
        user_id=user_id,
        workflow_run_id=queued.workflow_run_id,
        max_results=body.max_results,
    )
    return DiscoverJobsResponse(
        workflow_run_id=queued.workflow_run_id,
        task_id=task_id,
        status=queued.status,
        idempotency_key=queued.idempotency_key,
    )


@router.get("", response_model=list[JobMatchSummaryResponse])
def list_jobs(
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> list[JobMatchSummaryResponse]:
    rows = _listing(session, user_id).list_matches()
    return [_to_summary(row) for row in rows]


@router.get("/{match_id}", response_model=JobMatchDetailResponse)
def get_job(
    match_id: UUID,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> JobMatchDetailResponse:
    row = _listing(session, user_id).get_match_detail(match_id)
    return _to_detail(row)


@router.post("/{match_id}/score", response_model=JobMatchDetailResponse)
def rescore_job(
    match_id: UUID,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> JobMatchDetailResponse:
    row = _listing(session, user_id).rescore_match(match_id)
    return _to_detail(row)
