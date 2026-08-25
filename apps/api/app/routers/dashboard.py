"""Dashboard summary API."""

from __future__ import annotations

from fastapi import APIRouter

from app.dependencies import CurrentUserIdDep, DbSessionDep
from app.schemas.saas import DashboardSummaryResponse
from packages.domain.dashboard import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> DashboardSummaryResponse:
    summary = DashboardService(session, user_id).summary()
    return DashboardSummaryResponse(**summary.model_dump())
