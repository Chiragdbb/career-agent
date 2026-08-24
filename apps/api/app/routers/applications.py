from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.dependencies import CurrentUserIdDep, DbSessionDep
from app.schemas import ApplicationResponse
from packages.domain.tenant_resources import TenantResourceService

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("", response_model=list[ApplicationResponse])
def list_applications(
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> list[ApplicationResponse]:
    rows = TenantResourceService(session, user_id).list_applications()
    return [
        ApplicationResponse(
            id=row.id,
            job_id=row.job_id,
            status=row.status.value if hasattr(row.status, "value") else str(row.status),
        )
        for row in rows
    ]


@router.get("/{application_id}", response_model=ApplicationResponse)
def get_application(
    application_id: UUID,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> ApplicationResponse:
    row = TenantResourceService(session, user_id).get_application(application_id)
    return ApplicationResponse(
        id=row.id,
        job_id=row.job_id,
        status=row.status.value if hasattr(row.status, "value") else str(row.status),
    )
