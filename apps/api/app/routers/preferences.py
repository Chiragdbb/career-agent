from __future__ import annotations

from fastapi import APIRouter

from app.dependencies import CurrentUserIdDep, DbSessionDep
from app.schemas.preferences import PreferencesResponse, PreferencesUpdateRequest
from packages.domain.preferences import PreferencesService

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("", response_model=PreferencesResponse)
def get_preferences(
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> PreferencesResponse:
    service = PreferencesService(session, user_id)
    row = service.get_or_create()
    return PreferencesResponse(
        id=row.id,
        user_id=row.user_id,
        status=row.status.value if hasattr(row.status, "value") else str(row.status),
        settings=service.get_settings(),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.put("", response_model=PreferencesResponse)
def update_preferences(
    body: PreferencesUpdateRequest,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> PreferencesResponse:
    service = PreferencesService(session, user_id)
    row = service.update(body.settings)
    return PreferencesResponse(
        id=row.id,
        user_id=row.user_id,
        status=row.status.value if hasattr(row.status, "value") else str(row.status),
        settings=body.settings,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
