"""Activity log API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.dependencies import CurrentUserIdDep, DbSessionDep
from packages.domain.activity_log import ActivityLogService

router = APIRouter(prefix="/activity", tags=["activity"])


class ActivityStepResponse(BaseModel):
    id: str
    timestamp: datetime
    step: str
    phase: str
    message: str
    display: dict | None = None


class ActivityRunResponse(BaseModel):
    id: UUID
    workflow_type: str
    status: str
    message: str
    human_title: str | None = None
    metadata: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    error: str | None = None
    eta_label: str | None = None
    steps: list[ActivityStepResponse] = Field(default_factory=list)


class ActivityEntryResponse(BaseModel):
    id: str
    timestamp: datetime
    entry_type: str
    message: str
    workflow_run_id: UUID | None = None
    workflow_type: str | None = None
    metadata: dict | None = None


@router.get("", response_model=list[ActivityRunResponse])
def list_activity(
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
    before: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[ActivityRunResponse]:
    rows = ActivityLogService(session, user_id).list_runs(before=before, limit=limit)
    return [
        ActivityRunResponse(
            id=row.id,
            workflow_type=row.workflow_type,
            status=row.status,
            message=row.message,
            human_title=row.human_title,
            metadata=row.metadata,
            created_at=row.created_at,
            updated_at=row.updated_at,
            error=row.error,
            eta_label=row.eta_label,
            steps=[
                ActivityStepResponse(
                    id=s.id,
                    timestamp=s.timestamp,
                    step=s.step,
                    phase=s.phase,
                    message=s.message,
                    display=s.display,
                )
                for s in row.steps
            ],
        )
        for row in rows
    ]


@router.get("/flat", response_model=list[ActivityEntryResponse])
def list_activity_flat(
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
    before: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[ActivityEntryResponse]:
    rows = ActivityLogService(session, user_id).list_entries(before=before, limit=limit)
    return [
        ActivityEntryResponse(
            id=row.id,
            timestamp=row.timestamp,
            entry_type=row.entry_type,
            message=row.message,
            workflow_run_id=row.workflow_run_id,
            workflow_type=row.workflow_type,
            metadata=row.metadata,
        )
        for row in rows
    ]
