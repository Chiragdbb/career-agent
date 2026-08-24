from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.dependencies import CurrentUserIdDep, DbSessionDep
from app.schemas import ResumeResponse
from packages.domain.tenant_resources import TenantResourceService

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.get("", response_model=list[ResumeResponse])
def list_resumes(
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> list[ResumeResponse]:
    rows = TenantResourceService(session, user_id).list_resumes()
    return [
        ResumeResponse(
            id=row.id,
            name=row.name,
            status=row.status.value if hasattr(row.status, "value") else str(row.status),
        )
        for row in rows
    ]


@router.get("/{resume_id}", response_model=ResumeResponse)
def get_resume(
    resume_id: UUID,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> ResumeResponse:
    row = TenantResourceService(session, user_id).get_resume(resume_id)
    return ResumeResponse(
        id=row.id,
        name=row.name,
        status=row.status.value if hasattr(row.status, "value") else str(row.status),
    )
