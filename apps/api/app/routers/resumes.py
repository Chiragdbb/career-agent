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
from packages.domain.ats_score import AtsScoreService
from packages.domain.exceptions import NotFoundError
from packages.domain.preferences import PreferencesService
from packages.domain.resumes import ResumeService, ResumeUploadInput
from database.models.schema import Resume, ResumeVersion

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


@router.post("/{resume_id}/ats-score")
def score_resume_ats(
    resume_id: UUID,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> dict:
    resume = (
        session.query(Resume)
        .filter(Resume.id == resume_id, Resume.user_id == user_id)
        .one_or_none()
    )
    if resume is None:
        raise NotFoundError("Resume not found")
    version = (
        session.query(ResumeVersion)
        .filter(ResumeVersion.resume_id == resume.id, ResumeVersion.user_id == user_id)
        .order_by(ResumeVersion.created_at.desc())
        .first()
    )
    if version is None or not version.plain_text:
        raise NotFoundError("Resume text not available yet")

    prefs = PreferencesService(session, user_id).get_settings()
    skills: list[str] = []
    if isinstance(version.sections, dict):
        raw_skills = version.sections.get("skills")
        if isinstance(raw_skills, list):
            skills = [str(s) for s in raw_skills if s]

    result = AtsScoreService().score_against_preferences(
        version.plain_text,
        target_roles=list(prefs.target_roles or []),
        skills=skills or list(prefs.industries or []),
    )
    return {
        "score": result.score,
        "matched": result.matched,
        "missing": result.missing,
        "keywords": result.keywords,
        "credit_warning": result.score < 90,
        "warning": (
            "A lower-ATS base resume will use more credits when customizing for each job."
            if result.score < 90
            else None
        ),
    }


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
