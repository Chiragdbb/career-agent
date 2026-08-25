"""Human tasks API — list and resolve intervention items."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.dependencies import CurrentUserIdDep, DbSessionDep
from app.schemas.human_tasks import HumanTaskResolveRequest, HumanTaskResponse
from database.models.enums import HumanTaskStatus
from packages.domain.career_workflow import CareerWorkflowService, CareerWorkflowStart
from packages.domain.human_tasks import HumanTaskResolveInput, HumanTaskService
from packages.providers.notification import MockNotificationProvider

router = APIRouter(prefix="/human-tasks", tags=["human-tasks"])


def _notifications():
    return MockNotificationProvider()


@router.get("", response_model=list[HumanTaskResponse])
def list_human_tasks(
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
    status: str | None = Query(default="open"),
) -> list[HumanTaskResponse]:
    status_enum: HumanTaskStatus | None = None
    if status:
        status_enum = HumanTaskStatus(status)
    rows = HumanTaskService(session, user_id, notifications=_notifications()).list_tasks(
        status=status_enum
    )
    return [
        HumanTaskResponse(
            id=r.id,
            task_type=r.task_type,
            title=r.title,
            status=r.status,
            details=r.details,
            application_id=r.application_id,
            outreach_id=r.outreach_id,
            workflow_run_id=r.workflow_run_id,
            resolution=r.resolution,
        )
        for r in rows
    ]


@router.post("/{task_id}/resolve", response_model=HumanTaskResponse)
def resolve_human_task(
    task_id: UUID,
    body: HumanTaskResolveRequest,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> HumanTaskResponse:
    service = HumanTaskService(session, user_id, notifications=_notifications())
    view = service.resolve(
        task_id,
        HumanTaskResolveInput(
            resolution=body.resolution,
            resume_workflow=body.resume_workflow,
            notes=body.notes,
        ),
    )

    # If linked to a career workflow, resume orchestration after approval.
    if body.resume_workflow and view.workflow_run_id is not None:
        from database.models.schema import WorkflowRun

        run = (
            session.query(WorkflowRun)
            .filter(WorkflowRun.id == view.workflow_run_id, WorkflowRun.user_id == user_id)
            .one_or_none()
        )
        if run is not None:
            meta = run.metadata_json if isinstance(run.metadata_json, dict) else {}
            match_id = meta.get("job_match_id")
            if match_id:
                CareerWorkflowService(
                    session, user_id, notifications=_notifications()
                ).start_or_resume(
                    CareerWorkflowStart(
                        job_match_id=UUID(match_id),
                        permit_submit=bool(meta.get("permit_submit")),
                        force=True,
                    )
                )

    # Re-fetch in case workflow mutated related state.
    view = service.get(task_id)
    return HumanTaskResponse(
        id=view.id,
        task_type=view.task_type,
        title=view.title,
        status=view.status,
        details=view.details,
        application_id=view.application_id,
        outreach_id=view.outreach_id,
        workflow_run_id=view.workflow_run_id,
        resolution=view.resolution,
    )
