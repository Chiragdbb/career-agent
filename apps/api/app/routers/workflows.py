from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.dependencies import CurrentUserIdDep, DbSessionDep
from app.schemas.jobs import WorkflowRunResponse
from packages.domain.jobs import DiscoveryTriggerService

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("/{run_id}", response_model=WorkflowRunResponse)
def get_workflow_run(
    run_id: UUID,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> WorkflowRunResponse:
    row = DiscoveryTriggerService(session, user_id).get_run(run_id)
    return WorkflowRunResponse(
        id=row.id,
        workflow_type=row.workflow_type,
        status=row.status.value if hasattr(row.status, "value") else str(row.status),
        error=row.error,
        metadata=row.metadata_json if isinstance(row.metadata_json, dict) else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
