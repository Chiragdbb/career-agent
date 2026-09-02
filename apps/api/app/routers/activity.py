"""Activity log API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.dependencies import CurrentUserIdDep, DbSessionDep
from packages.domain.activity_log import ActivityLogService

router = APIRouter(prefix="/activity", tags=["activity"])


class ActivityEntryResponse(BaseModel):
    id: str
    timestamp: datetime
    entry_type: str
    message: str
    workflow_run_id: UUID | None = None
    workflow_type: str | None = None
    metadata: dict | None = None


@router.get("", response_model=list[ActivityEntryResponse])
def list_activity(
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
