"""Follow-ups API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.dependencies import CurrentUserIdDep, DbSessionDep
from app.schemas.saas import FollowUpResponse, FollowUpScheduleRequest
from database.models.enums import FollowUpStatus
from packages.domain.follow_ups import FollowUpScheduleInput, FollowUpService
from packages.providers.notification import MockNotificationProvider

router = APIRouter(prefix="/follow-ups", tags=["follow-ups"])


def _service(session, user_id) -> FollowUpService:
    return FollowUpService(
        session, user_id, notifications=MockNotificationProvider()
    )


@router.get("", response_model=list[FollowUpResponse])
def list_follow_ups(
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
    status: str | None = Query(default=None),
) -> list[FollowUpResponse]:
    status_enum = FollowUpStatus(status) if status else None
    rows = _service(session, user_id).list_follow_ups(status=status_enum)
    return [FollowUpResponse(**r.model_dump()) for r in rows]


@router.post("", response_model=FollowUpResponse, status_code=201)
def schedule_follow_up(
    body: FollowUpScheduleRequest,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> FollowUpResponse:
    view = _service(session, user_id).schedule(
        FollowUpScheduleInput(**body.model_dump())
    )
    return FollowUpResponse(**view.model_dump())


@router.post("/process-due", response_model=list[FollowUpResponse])
def process_due_follow_ups(
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> list[FollowUpResponse]:
    rows = _service(session, user_id).process_due()
    return [FollowUpResponse(**r.model_dump()) for r in rows]


@router.get("/{follow_up_id}", response_model=FollowUpResponse)
def get_follow_up(
    follow_up_id: UUID,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> FollowUpResponse:
    view = _service(session, user_id).get(follow_up_id)
    return FollowUpResponse(**view.model_dump())
