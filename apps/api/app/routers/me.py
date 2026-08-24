from __future__ import annotations

from fastapi import APIRouter

from app.dependencies import CurrentUserDep
from app.schemas import MeResponse

router = APIRouter(tags=["auth"])


@router.get("/me", response_model=MeResponse)
def me(user: CurrentUserDep) -> MeResponse:
    """Return the authenticated local user (creates the row on first login)."""
    return MeResponse(
        id=user.id,
        auth_subject=user.auth_subject,
        status=user.status.value if hasattr(user.status, "value") else str(user.status),
    )
