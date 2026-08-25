"""Documents and analytics thin read APIs."""

from __future__ import annotations

from fastapi import APIRouter

from app.dependencies import CurrentUserIdDep, DbSessionDep
from app.schemas.saas import AnalyticsSummaryResponse, DocumentResponse
from packages.domain.dashboard import DashboardService

documents_router = APIRouter(prefix="/documents", tags=["documents"])
analytics_router = APIRouter(prefix="/analytics", tags=["analytics"])


@documents_router.get("", response_model=list[DocumentResponse])
def list_documents(
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> list[DocumentResponse]:
    rows = DashboardService(session, user_id).list_documents()
    return [DocumentResponse(**r) for r in rows]


@analytics_router.get("/summary", response_model=AnalyticsSummaryResponse)
def analytics_summary(
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> AnalyticsSummaryResponse:
    summary = DashboardService(session, user_id).summary()
    return AnalyticsSummaryResponse(
        jobs_count=summary.jobs_count,
        applications_count=summary.applications_count,
        contacts_count=summary.contacts_count,
        outreach_count=summary.outreach_count,
        interviews_count=summary.upcoming_interviews,
        offers_count=summary.pending_offers,
        open_human_tasks=summary.open_human_tasks,
        unread_notifications=summary.unread_notifications,
    )
