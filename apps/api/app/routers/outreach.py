from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.dependencies import CurrentUserIdDep, DbSessionDep
from app.schemas import OutreachResponse
from packages.domain.tenant_resources import TenantResourceService

router = APIRouter(prefix="/outreach", tags=["outreach"])


@router.get("", response_model=list[OutreachResponse])
def list_outreach(
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> list[OutreachResponse]:
    rows = TenantResourceService(session, user_id).list_outreach()
    return [
        OutreachResponse(
            id=row.id,
            contact_id=row.contact_id,
            status=row.status.value if hasattr(row.status, "value") else str(row.status),
            subject=row.subject,
        )
        for row in rows
    ]


@router.get("/{outreach_id}", response_model=OutreachResponse)
def get_outreach(
    outreach_id: UUID,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> OutreachResponse:
    row = TenantResourceService(session, user_id).get_outreach(outreach_id)
    return OutreachResponse(
        id=row.id,
        contact_id=row.contact_id,
        status=row.status.value if hasattr(row.status, "value") else str(row.status),
        subject=row.subject,
    )
