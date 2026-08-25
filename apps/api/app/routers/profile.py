from __future__ import annotations

from fastapi import APIRouter

from app.dependencies import CurrentUserIdDep, DbSessionDep
from app.schemas.profile import ProfileResponse, ProfileUpdateRequest
from packages.domain.profile import ProfileData, ProfileService

router = APIRouter(prefix="/profile", tags=["profile"])


def _to_response(row) -> ProfileResponse:
    return ProfileResponse(
        id=row.id,
        user_id=row.user_id,
        status=row.status.value if hasattr(row.status, "value") else str(row.status),
        display_name=row.display_name,
        headline=row.headline,
        location=row.location,
        linkedin_url=row.linkedin_url,
        summary=row.summary,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=ProfileResponse)
def get_profile(
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> ProfileResponse:
    row = ProfileService(session, user_id).get_or_create()
    return _to_response(row)


@router.put("", response_model=ProfileResponse)
def update_profile(
    body: ProfileUpdateRequest,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> ProfileResponse:
    data = ProfileData(
        display_name=body.display_name,
        headline=body.headline,
        location=body.location,
        linkedin_url=body.linkedin_url,
        summary=body.summary,
    )
    row = ProfileService(session, user_id).update(data)
    return _to_response(row)
