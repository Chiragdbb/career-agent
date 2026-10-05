from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks

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
    RescrapeJobResponse,
    ScoreBreakdownResponse,
    WorkflowRunResponse,
)
from packages.domain.discovery_lock import DiscoveryLock
from packages.domain.career_workflow import CareerWorkflowStart
from packages.domain.career_workflow_factory import build_career_workflow_service
from packages.domain.jobs import DiscoveryTriggerService, JobListingService, JobRescrapeTriggerService
from packages.domain.dashboard import DashboardService
from packages.domain.events import UserEventType
from packages.domain.exceptions import DomainError
from database.models.enums import JobMatchStatus
from packages.providers.notification import MockNotificationProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _run_career_pipeline_background(
    user_id: UUID,
    match_id: UUID,
    *,
    force: bool,
) -> None:
    """Execute a prepared career pipeline outside the HTTP request."""
    from app.database import get_session_factory, init_db
    from app.redis import get_redis
    from packages.domain.career_workflow_factory import build_career_workflow_service
    from packages.domain.workflow_cancellation import WorkflowCancellation
    from packages.providers.notification import MockNotificationProvider

    init_db()
    session = get_session_factory()()
    try:
        try:
            redis_client = get_redis()
        except Exception:
            redis_client = None
        cancellation = WorkflowCancellation(redis_client)
        service = build_career_workflow_service(
            session,
            user_id,
            notifications=MockNotificationProvider(),
            cancellation=cancellation,
        )
        service.start_or_resume(
            CareerWorkflowStart(
                job_match_id=match_id,
                permit_submit=False,
                force=force,
                execute=True,
            )
        )
    except Exception:
        logger.exception(
            "background career pipeline failed user=%s match=%s", user_id, match_id
        )
    finally:
        session.close()


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
        application_id=getattr(row, "application_id", None),
        rationale=getattr(row, "rationale", None),
    )


def _to_detail(row) -> JobMatchDetailResponse:
    from packages.domain.job_ingest.text_sanitize import strip_html_to_text

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
    raw_desc = row.description
    description = strip_html_to_text(raw_desc) if isinstance(raw_desc, str) else raw_desc
    requirements = [
        strip_html_to_text(str(r)) for r in (row.requirements or []) if r
    ]
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
        description=description,
        job_skills=row.job_skills,
        matched_skills=row.matched_skills,
        possible_matches=row.possible_matches,
        missing_skills=row.missing_skills,
        score_breakdown=breakdown,
        explanation=row.explanation,
        created_at=row.created_at,
        company_domain=row.company_domain,
        source=row.source,
        external_id=row.external_id,
        employment_type=row.employment_type,
        remote_type=row.remote_type,
        seniority=row.seniority,
        salary_min=row.salary_min,
        salary_max=row.salary_max,
        salary_currency=row.salary_currency,
        requirements=requirements,
        posted_at=row.posted_at,
        last_scraped_at=row.last_scraped_at,
        scraped_at=row.scraped_at,
        job_status=row.job_status,
        completeness_score=row.completeness_score,
        missing_fields=row.missing_fields or [],
        extraction_provenance=row.extraction_provenance,
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
    discovery_lock = DiscoveryLock(redis_client)
    trigger = DiscoveryTriggerService(session, user_id, discovery_lock=discovery_lock)
    queued = trigger.enqueue(
        idempotency_key=body.idempotency_key,
        max_results=body.max_results,
        discovery_mode=body.mode,
        query_hint=body.query_hint,
    )
    try:
        task_id = task_client.enqueue_discover_jobs(
            user_id=user_id,
            workflow_run_id=queued.workflow_run_id,
            max_results=body.max_results,
        )
    except Exception as exc:
        from workers.discovery.tasks import _mark_run_failed

        _mark_run_failed(session, user_id, queued.workflow_run_id, exc)
        discovery_lock.release(user_id)
        raise
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
                "mode": body.mode,
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
    events: EventPublisherDep,
    redis_client: RedisDep,
    background_tasks: BackgroundTasks,
) -> dict:
    from database.models.schema import JobMatch
    from packages.domain.workflow_cancellation import WorkflowCancellation

    service = _listing(session, user_id)
    if body.action == "save":
        updated = service.bulk_update_status(body.match_ids, JobMatchStatus.saved)
        return {"action": body.action, "updated": len(updated), "matches": [_to_summary(r) for r in updated]}
    if body.action == "dismiss":
        updated = service.bulk_update_status(body.match_ids, JobMatchStatus.dismissed)
        return {"action": body.action, "updated": len(updated), "matches": [_to_summary(r) for r in updated]}
    if body.action == "start_pipeline":
        cancellation = WorkflowCancellation(redis_client)
        results = []
        already_running: list[dict] = []
        errors: list[dict] = []
        for match_id in body.match_ids:
            try:
                match = (
                    session.query(JobMatch)
                    .filter(JobMatch.id == match_id, JobMatch.user_id == user_id)
                    .one_or_none()
                )
                if match is None:
                    errors.append({"match_id": str(match_id), "error": "Job match not found"})
                    continue
                if match.status == JobMatchStatus.applied and not body.force:
                    errors.append(
                        {
                            "match_id": str(match_id),
                            "error": (
                                "Already applied — return this job to the pile "
                                "before starting a new application."
                            ),
                        }
                    )
                    continue
                workflow = build_career_workflow_service(
                    session,
                    user_id,
                    events=events,
                    notifications=MockNotificationProvider(),
                    cancellation=cancellation,
                )
                queued = workflow.start_or_resume(
                    CareerWorkflowStart(
                        job_match_id=match_id,
                        permit_submit=False,
                        force=body.force,
                        execute=False,
                    )
                )
                dumped = queued.model_dump(mode="json")
                if queued.already_running or queued.paused:
                    already_running.append(dumped)
                    continue
                # Only enqueue Celery when that is the configured backend. In
                # QStash/inline production there is often no Celery worker, so
                # .delay() would leave the run queued forever with no executor.
                enqueued = False
                from app.config import get_settings

                if get_settings().resolved_task_backend() == "celery":
                    try:
                        from workers.applications.tasks import run_career_workflow

                        async_result = run_career_workflow.delay(
                            str(user_id),
                            str(match_id),
                            False,
                            bool(body.force),
                        )
                        from database.models.schema import WorkflowRun

                        run_row = session.get(WorkflowRun, queued.workflow_run_id)
                        if run_row is not None:
                            meta = dict(run_row.metadata_json or {})
                            meta["task_id"] = str(async_result.id)
                            run_row.metadata_json = meta
                            session.commit()
                            dumped["task_id"] = str(async_result.id)
                        enqueued = True
                    except Exception:
                        logger.info(
                            "celery enqueue unavailable; using BackgroundTasks match=%s",
                            match_id,
                        )
                if not enqueued:
                    background_tasks.add_task(
                        _run_career_pipeline_background,
                        user_id,
                        match_id,
                        force=bool(body.force),
                    )
                results.append(dumped)
            except DomainError as exc:
                errors.append({"match_id": str(match_id), "error": str(exc)})
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                errors.append({"match_id": str(match_id), "error": str(exc)})
        return {
            "action": body.action,
            "started": len(results),
            "already_running": len(already_running),
            "workflows": results,
            "existing": already_running,
            "errors": errors,
        }
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


@router.post("/{match_id}/rescrape", response_model=RescrapeJobResponse, status_code=202)
def rescrape_job(
    match_id: UUID,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
    task_client: DiscoveryTaskClientDep,
    events: EventPublisherDep,
) -> RescrapeJobResponse:
    trigger = JobRescrapeTriggerService(session, user_id)
    queued = trigger.enqueue(match_id)
    task_id = task_client.enqueue_rescrape_job(
        user_id=user_id,
        workflow_run_id=queued.workflow_run_id,
        match_id=match_id,
    )
    trigger.attach_task_id(queued.workflow_run_id, task_id)
    events.publish(
        user_id,
        UserEventType.workflow_progress,
        {
            "workflow_run_id": str(queued.workflow_run_id),
            "workflow_type": "job_rescrape",
            "step": "queued",
            "message": "Re-scrape queued",
            "data": {
                "task_id": task_id,
                "status": "queued",
                "match_id": str(match_id),
            },
        },
    )
    return RescrapeJobResponse(
        workflow_run_id=queued.workflow_run_id,
        task_id=task_id,
        status=queued.status,
        match_id=match_id,
    )


@router.post("/{match_id}/score", response_model=JobMatchDetailResponse)
def rescore_job(
    match_id: UUID,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> JobMatchDetailResponse:
    row = _listing(session, user_id).rescore_match(match_id)
    return _to_detail(row)
