from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.dependencies import CurrentUserIdDep, DbSessionDep, EventPublisherDep, RedisDep
from app.schemas.human_tasks import CareerWorkflowResponse, CareerWorkflowStartRequest
from app.schemas.jobs import WorkflowRunResponse, WorkflowTaskResponse
from packages.domain.career_workflow import CareerWorkflowService, CareerWorkflowStart
from packages.domain.events import UserEventType
from packages.domain.discovery_lock import DiscoveryLock
from packages.domain.jobs import DiscoveryTriggerService
from packages.domain.workflow_cancellation import WorkflowCancellation
from packages.domain.workflows import WorkflowObservabilityService
from packages.providers.notification import MockNotificationProvider

router = APIRouter(prefix="/workflows", tags=["workflows"])


def _to_run_response(row) -> WorkflowRunResponse:
    return WorkflowRunResponse(
        id=row.id,
        workflow_type=row.workflow_type,
        status=row.status,
        error=row.error,
        metadata=row.metadata,
        created_at=row.created_at,
        updated_at=row.updated_at,
        task_count=row.task_count,
        completed_task_count=row.completed_task_count,
        failed_task_count=row.failed_task_count,
    )


def _to_task_response(row) -> WorkflowTaskResponse:
    return WorkflowTaskResponse(
        id=row.id,
        workflow_run_id=row.workflow_run_id,
        task_type=row.task_type,
        status=row.status,
        input_payload=row.input_payload,
        output_payload=row.output_payload,
        error=row.error,
        attempt=row.attempt,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=list[WorkflowRunResponse])
def list_workflow_runs(
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
    limit: int = Query(default=20, ge=1, le=50),
    active_only: bool = Query(default=False),
) -> list[WorkflowRunResponse]:
    service = WorkflowObservabilityService(session, user_id)
    rows = service.list_runs(limit=limit, active_only=active_only)
    return [_to_run_response(row) for row in rows]


@router.post("/career", response_model=CareerWorkflowResponse)
def start_career_workflow(
    body: CareerWorkflowStartRequest,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> CareerWorkflowResponse:
    result = CareerWorkflowService(
        session, user_id, notifications=MockNotificationProvider()
    ).start_or_resume(
        CareerWorkflowStart(
            job_match_id=body.job_match_id,
            permit_submit=body.permit_submit,
            resume_version_id=body.resume_version_id,
            force=body.force,
        )
    )
    return CareerWorkflowResponse(**result.model_dump())


@router.get("/{run_id}", response_model=WorkflowRunResponse)
def get_workflow_run(
    run_id: UUID,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> WorkflowRunResponse:
    row = WorkflowObservabilityService(session, user_id).get_run(run_id)
    return _to_run_response(row)


@router.get("/{run_id}/tasks", response_model=list[WorkflowTaskResponse])
def list_workflow_tasks(
    run_id: UUID,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> list[WorkflowTaskResponse]:
    rows = WorkflowObservabilityService(session, user_id).list_tasks(run_id)
    return [_to_task_response(row) for row in rows]


@router.post("/{run_id}/cancel", response_model=WorkflowRunResponse)
def cancel_workflow_run(
    run_id: UUID,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
    redis_client: RedisDep,
    events: EventPublisherDep,
) -> WorkflowRunResponse:
    cancellation = WorkflowCancellation(redis_client)
    trigger = DiscoveryTriggerService(session, user_id, discovery_lock=DiscoveryLock(redis_client))
    run = trigger.cancel(run_id, cancellation=cancellation)

    metadata = dict(run.metadata_json or {})
    task_id = metadata.get("task_id")
    if task_id and not str(task_id).startswith("inline-"):
        try:
            from workers.celery_app import celery_app

            celery_app.control.revoke(str(task_id), terminate=True)
        except Exception:
            pass

    events.publish(
        user_id,
        UserEventType.workflow_progress,
        {
            "workflow_run_id": str(run_id),
            "workflow_type": run.workflow_type,
            "step": "cancelling",
            "message": "Cancellation requested",
            "data": {"status": "cancelling"},
        },
    )
    row = WorkflowObservabilityService(session, user_id).get_run(run_id)
    return _to_run_response(row)
