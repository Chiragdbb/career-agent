"""Interviews and offers API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.dependencies import CurrentUserIdDep, DbSessionDep
from app.schemas.saas import (
    InterviewCreateRequest,
    InterviewResponse,
    InterviewUpdateRequest,
    OfferCreateRequest,
    OfferResponse,
    OfferUpdateRequest,
)
from database.models.enums import InterviewStatus, OfferStatus
from packages.domain.interviews import (
    InterviewCreate,
    InterviewService,
    InterviewUpdate,
    OfferCreate,
    OfferService,
    OfferUpdate,
)

interviews_router = APIRouter(prefix="/interviews", tags=["interviews"])
offers_router = APIRouter(prefix="/offers", tags=["offers"])


@interviews_router.get("", response_model=list[InterviewResponse])
def list_interviews(
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
    application_id: UUID | None = Query(default=None),
) -> list[InterviewResponse]:
    rows = InterviewService(session, user_id).list_interviews(
        application_id=application_id
    )
    return [InterviewResponse(**r.model_dump()) for r in rows]


@interviews_router.post("", response_model=InterviewResponse, status_code=201)
def create_interview(
    body: InterviewCreateRequest,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> InterviewResponse:
    view = InterviewService(session, user_id).create(
        InterviewCreate(
            application_id=body.application_id,
            title=body.title,
            scheduled_at=body.scheduled_at,
            notes=body.notes,
            round=body.round,
            format=body.format,
            interviewer=body.interviewer,
            status=InterviewStatus(body.status),
        )
    )
    return InterviewResponse(**view.model_dump())


@interviews_router.get("/{interview_id}", response_model=InterviewResponse)
def get_interview(
    interview_id: UUID,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> InterviewResponse:
    view = InterviewService(session, user_id).get(interview_id)
    return InterviewResponse(**view.model_dump())


@interviews_router.patch("/{interview_id}", response_model=InterviewResponse)
def update_interview(
    interview_id: UUID,
    body: InterviewUpdateRequest,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> InterviewResponse:
    data = body.model_dump(exclude_unset=True)
    if "status" in data and data["status"] is not None:
        data["status"] = InterviewStatus(data["status"])
    view = InterviewService(session, user_id).update(
        interview_id, InterviewUpdate(**data)
    )
    return InterviewResponse(**view.model_dump())


@offers_router.get("", response_model=list[OfferResponse])
def list_offers(
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
    application_id: UUID | None = Query(default=None),
) -> list[OfferResponse]:
    rows = OfferService(session, user_id).list_offers(application_id=application_id)
    return [OfferResponse(**r.model_dump()) for r in rows]


@offers_router.post("", response_model=OfferResponse, status_code=201)
def create_offer(
    body: OfferCreateRequest,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> OfferResponse:
    view = OfferService(session, user_id).create(
        OfferCreate(
            application_id=body.application_id,
            compensation=body.compensation,
            equity=body.equity,
            location=body.location,
            deadline=body.deadline,
            status=OfferStatus(body.status),
            details=body.details,
        )
    )
    return OfferResponse(**view.model_dump())


@offers_router.get("/{offer_id}", response_model=OfferResponse)
def get_offer(
    offer_id: UUID,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> OfferResponse:
    view = OfferService(session, user_id).get(offer_id)
    return OfferResponse(**view.model_dump())


@offers_router.patch("/{offer_id}", response_model=OfferResponse)
def update_offer(
    offer_id: UUID,
    body: OfferUpdateRequest,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> OfferResponse:
    data = body.model_dump(exclude_unset=True)
    if "status" in data and data["status"] is not None:
        data["status"] = OfferStatus(data["status"])
    view = OfferService(session, user_id).update(offer_id, OfferUpdate(**data))
    return OfferResponse(**view.model_dump())
