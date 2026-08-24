from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.dependencies import CurrentUserIdDep, DbSessionDep
from app.schemas import JobMatchResponse
from packages.domain.tenant_resources import TenantResourceService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobMatchResponse])
def list_jobs(
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> list[JobMatchResponse]:
    rows = TenantResourceService(session, user_id).list_jobs()
    return [
        JobMatchResponse(
            id=row.id,
            job_id=row.job_id,
            status=row.status.value if hasattr(row.status, "value") else str(row.status),
            score=row.score,
        )
        for row in rows
    ]


@router.get("/{job_id}", response_model=JobMatchResponse)
def get_job(
    job_id: UUID,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> JobMatchResponse:
    # User-facing "jobs" are tenant-scoped job_matches (shared Job rows are not).
    row = TenantResourceService(session, user_id).get_job(job_id)
    return JobMatchResponse(
        id=row.id,
        job_id=row.job_id,
        status=row.status.value if hasattr(row.status, "value") else str(row.status),
        score=row.score,
    )
