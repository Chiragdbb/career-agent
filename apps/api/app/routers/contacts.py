from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.dependencies import CurrentUserIdDep, DbSessionDep
from app.schemas import ContactResponse
from packages.domain.tenant_resources import TenantResourceService

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("", response_model=list[ContactResponse])
def list_contacts(
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> list[ContactResponse]:
    rows = TenantResourceService(session, user_id).list_contacts()
    return [
        ContactResponse(
            id=row.id,
            name=row.name,
            status=row.status.value if hasattr(row.status, "value") else str(row.status),
        )
        for row in rows
    ]


@router.get("/{contact_id}", response_model=ContactResponse)
def get_contact(
    contact_id: UUID,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> ContactResponse:
    row = TenantResourceService(session, user_id).get_contact(contact_id)
    return ContactResponse(
        id=row.id,
        name=row.name,
        status=row.status.value if hasattr(row.status, "value") else str(row.status),
    )
