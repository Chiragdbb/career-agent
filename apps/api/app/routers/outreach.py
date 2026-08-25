from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.dependencies import CurrentUserIdDep, DbSessionDep
from app.schemas import OutreachResponse
from app.schemas.human_tasks import OutreachDetailResponse, OutreachDraftRequest
from packages.domain.outreach import OutreachDraftInput, OutreachService, OutreachType
from packages.providers.email_sender import MockEmailSenderProvider
from packages.providers.notification import MockNotificationProvider
from packages.domain.tenant_resources import TenantResourceService

router = APIRouter(prefix="/outreach", tags=["outreach"])


def _outreach_service(session, user_id) -> OutreachService:
    return OutreachService(
        session,
        user_id,
        email_sender=MockEmailSenderProvider(),
        notifications=MockNotificationProvider(),
    )


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


@router.post("/drafts", response_model=OutreachDetailResponse)
def create_outreach_draft(
    body: OutreachDraftRequest,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> OutreachDetailResponse:
    view = _outreach_service(session, user_id).create_draft(
        OutreachDraftInput(
            contact_id=body.contact_id,
            outreach_type=OutreachType(body.outreach_type),
            subject=body.subject,
            body=body.body,
            reason=body.reason,
            application_id=body.application_id,
            job_id=body.job_id,
            company_id=body.company_id,
            recipient_email=body.recipient_email,
            request_approval=body.request_approval,
        )
    )
    return OutreachDetailResponse(**view.model_dump())


@router.post("/{outreach_id}/approve", response_model=OutreachDetailResponse)
def approve_outreach(
    outreach_id: UUID,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> OutreachDetailResponse:
    view = _outreach_service(session, user_id).approve(outreach_id)
    return OutreachDetailResponse(**view.model_dump())


@router.post("/{outreach_id}/send", response_model=OutreachDetailResponse)
def send_outreach(
    outreach_id: UUID,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> OutreachDetailResponse:
    view = _outreach_service(session, user_id).send(outreach_id)
    return OutreachDetailResponse(**view.model_dump())


@router.get("/{outreach_id}", response_model=OutreachDetailResponse)
def get_outreach(
    outreach_id: UUID,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> OutreachDetailResponse:
    view = _outreach_service(session, user_id).get(outreach_id)
    return OutreachDetailResponse(**view.model_dump())
