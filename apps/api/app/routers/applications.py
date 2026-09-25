from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.dependencies import CurrentUserIdDep, DbSessionDep
from app.schemas import ApplicationResponse
from app.schemas.saas import (
    ApplicationDetailResponse,
    ApplicationRefineRequest,
    ApplicationRefineResponse,
    ApplicationSummaryResponse,
)
from packages.domain.application_package import ApplicationPackageService
from packages.domain.application_refine import ApplicationRefineInput, ApplicationRefineService
from packages.domain.dashboard import DashboardService
from packages.domain.tenant_resources import TenantResourceService
from packages.providers.factory import create_llm_provider

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("", response_model=list[ApplicationSummaryResponse])
def list_applications(
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> list[ApplicationSummaryResponse]:
    rows = DashboardService(session, user_id).list_applications_enriched()
    return [ApplicationSummaryResponse.model_validate(r) for r in rows]


@router.get("/{application_id}", response_model=ApplicationDetailResponse)
def get_application(
    application_id: UUID,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> ApplicationDetailResponse:
    detail = DashboardService(session, user_id).get_application_detail(application_id)
    return ApplicationDetailResponse(
        id=detail.id,
        job_id=detail.job_id,
        status=detail.status,
        applied_at=detail.applied_at,
        resume_version_id=detail.resume_version_id,
        cover_letter_document_id=detail.cover_letter_document_id,
        submission_evidence=detail.submission_evidence,
        job_title=detail.job_title,
        company_name=detail.company_name,
        job_description=detail.job_description,
        job_url=detail.job_url,
        job_match_id=detail.job_match_id,
        contacts=detail.contacts,
        events=[e.model_dump(mode="json") for e in detail.events],
        documents=detail.documents,
        outreach=detail.outreach,
        follow_ups=detail.follow_ups,
        human_tasks=detail.human_tasks,
        interviews=detail.interviews,
        offers=detail.offers,
    )


@router.post("/{application_id}/return-to-pile")
def return_application_to_pile(
    application_id: UUID,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> dict:
    result = ApplicationPackageService(session, user_id).return_to_pile(application_id)
    return result.model_dump(mode="json")


@router.post("/{application_id}/dismiss")
def dismiss_application_package(
    application_id: UUID,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> dict:
    result = ApplicationPackageService(session, user_id).dismiss_package(application_id)
    return result.model_dump(mode="json")


@router.post(
    "/{application_id}/refine",
    response_model=ApplicationRefineResponse,
)
def refine_application(
    application_id: UUID,
    body: ApplicationRefineRequest,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> ApplicationRefineResponse:
    result = ApplicationRefineService(
        session, user_id, llm=create_llm_provider()
    ).refine(application_id, ApplicationRefineInput(prompt=body.prompt))
    return ApplicationRefineResponse(
        application_id=result.application_id,
        cover_letter=result.cover_letter,
        content=result.content,
        prompt=result.prompt,
    )


@router.get("/{application_id}/basic", response_model=ApplicationResponse)
def get_application_basic(
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
