from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.dependencies import (
    CurrentUserIdDep,
    DbSessionDep,
    DiscoveryTaskClientDep,
    EventPublisherDep,
    RedisDep,
)
from app.schemas.jobs import (
    DiscoverJobsRequest,
    DiscoverJobsResponse,
    JobBatchActionRequest,
    JobMatchDetailResponse,
    JobMatchSummaryResponse,
    JobMatchUpdateRequest,
    ScoreBreakdownResponse,
    WorkflowRunResponse,
)
from packages.domain.discovery_lock import DiscoveryLock
from packages.domain.career_workflow import CareerWorkflowService, CareerWorkflowStart
from packages.domain.jobs import DiscoveryTriggerService, JobListingService
from packages.domain.dashboard import DashboardService
from packages.domain.events import UserEventType
from packages.domain.exceptions import DomainError
from database.models.enums import JobMatchStatus
from packages.providers.notification import MockNotificationProvider

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
        is_new=row.is_new,
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
        possible_matches=row.possible_matches,
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
    events: EventPublisherDep,
    redis_client: RedisDep,
) -> DiscoverJobsResponse:
    trigger = DiscoveryTriggerService(session, user_id, discovery_lock=DiscoveryLock(redis_client))
    queued = trigger.enqueue(
        idempotency_key=body.idempotency_key,
        max_results=body.max_results,
    )
    task_id = task_client.enqueue_discover_jobs(
        user_id=user_id,
        workflow_run_id=queued.workflow_run_id,
        max_results=body.max_results,
    )
    trigger.attach_task_id(queued.workflow_run_id, task_id)
    events.publish(
        user_id,
        UserEventType.workflow_progress,
        {
            "workflow_run_id": str(queued.workflow_run_id),
            "workflow_type": "job_discovery",
            "step": "queued",
            "message": "Job discovery queued",
            "data": {
                "task_id": task_id,
                "status": "queued",
                "max_results": body.max_results,
            },
        },
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
    include_dismissed: bool = False,
) -> list[JobMatchSummaryResponse]:
    rows = _listing(session, user_id).list_matches(include_dismissed=include_dismissed)
    return [_to_summary(row) for row in rows]


@router.post("/actions/batch")
def batch_job_actions(
    body: JobBatchActionRequest,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> dict:
    service = _listing(session, user_id)
    if body.action == "save":
        updated = service.bulk_update_status(body.match_ids, JobMatchStatus.saved)
        return {"action": body.action, "updated": len(updated), "matches": [_to_summary(r) for r in updated]}
    if body.action == "dismiss":
        updated = service.bulk_update_status(body.match_ids, JobMatchStatus.dismissed)
        return {"action": body.action, "updated": len(updated), "matches": [_to_summary(r) for r in updated]}
    if body.action == "start_pipeline":
        workflow = CareerWorkflowService(
            session, user_id, notifications=MockNotificationProvider()
        )
        results = []
        for match_id in body.match_ids:
            result = workflow.start_or_resume(
                CareerWorkflowStart(job_match_id=match_id, permit_submit=False)
            )
            results.append(result.model_dump(mode="json"))
        return {"action": body.action, "started": len(results), "workflows": results}
    raise DomainError(f"Unknown action: {body.action}")


@router.patch("/{match_id}", response_model=JobMatchSummaryResponse)
def update_job(
    match_id: UUID,
    body: JobMatchUpdateRequest,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> JobMatchSummaryResponse:
    try:
        status = JobMatchStatus(body.status)
    except ValueError as exc:
        raise DomainError(f"Invalid status: {body.status}") from exc
    row = _listing(session, user_id).update_match_status(match_id, status)
    return _to_summary(row)


@router.get("/{match_id}", response_model=JobMatchDetailResponse)
def get_job(
    match_id: UUID,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> JobMatchDetailResponse:
    row = _listing(session, user_id).get_match_detail(match_id)
    return _to_detail(row)


@router.get("/{match_id}/workspace")
def get_job_workspace(
    match_id: UUID,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> dict:
    workspace = DashboardService(session, user_id).get_job_workspace(match_id)
    return workspace.model_dump(mode="json")


@router.post("/{match_id}/rescrape", response_model=JobMatchDetailResponse)
def rescrape_job(
    match_id: UUID,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> JobMatchDetailResponse:
    from packages.domain.job_rescrape import JobRescrapeService
    from packages.domain.llm_tasks import LLMTaskService
    from packages.providers.factory import create_extraction_llm_provider, create_llm_provider, create_scraper_provider

    llm = create_llm_provider()
    extraction_llm = create_extraction_llm_provider()
    service = JobRescrapeService(
        session,
        user_id,
        scraper=create_scraper_provider(),
        llm_tasks=LLMTaskService(llm, extraction_llm=extraction_llm),
    )
    service.rescrape(match_id)
    listing = _listing(session, user_id)
    listing.rescore_match(match_id)
    row = listing.get_match_detail(match_id)
    return _to_detail(row)


@router.post("/{match_id}/score", response_model=JobMatchDetailResponse)
def rescore_job(
    match_id: UUID,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> JobMatchDetailResponse:
    row = _listing(session, user_id).rescore_match(match_id)
    return _to_detail(row)
