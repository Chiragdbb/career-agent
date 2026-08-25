from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, File, Form, UploadFile

from app.dependencies import (
    CurrentUserIdDep,
    DbSessionDep,
    StorageBucketDep,
    StorageProviderDep,
)
from app.schemas.resumes import ResumeDetailResponse, ResumeSummaryResponse
from packages.domain.resumes import ResumeService, ResumeUploadInput

router = APIRouter(prefix="/resumes", tags=["resumes"])


def _service(
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
    storage: StorageProviderDep,
    bucket: StorageBucketDep,
) -> ResumeService:
    return ResumeService(session, user_id, storage, bucket=bucket)


@router.get("", response_model=list[ResumeSummaryResponse])
def list_resumes(
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
    storage: StorageProviderDep,
    bucket: StorageBucketDep,
) -> list[ResumeSummaryResponse]:
    rows = _service(session, user_id, storage, bucket).list_resumes()
    return [ResumeSummaryResponse.model_validate(row.model_dump()) for row in rows]


@router.get("/{resume_id}", response_model=ResumeDetailResponse)
def get_resume(
    resume_id: UUID,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
    storage: StorageProviderDep,
    bucket: StorageBucketDep,
) -> ResumeDetailResponse:
    detail = _service(session, user_id, storage, bucket).get_resume(
        resume_id,
        include_signed_url=True,
    )
    return ResumeDetailResponse.model_validate(detail.model_dump())


@router.post("", response_model=ResumeDetailResponse, status_code=201)
async def upload_resume(
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
    storage: StorageProviderDep,
    bucket: StorageBucketDep,
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    description: str | None = Form(default=None),
) -> ResumeDetailResponse:
    data = await file.read()
    detail = _service(session, user_id, storage, bucket).upload(
        ResumeUploadInput(
            filename=file.filename or "resume.bin",
            data=data,
            content_type=file.content_type,
            name=name,
            description=description,
        )
    )
    return ResumeDetailResponse.model_validate(detail.model_dump())
