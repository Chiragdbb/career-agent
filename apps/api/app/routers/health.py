from __future__ import annotations

from fastapi import APIRouter

from app.dependencies import CorrelationIdDep, DbSessionDep, RedisDep, SettingsDep
from app.schemas import HealthChecks, HealthResponse
from app.services.health import HealthService

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(
    settings: SettingsDep,
    session: DbSessionDep,
    redis_client: RedisDep,
    correlation_id: CorrelationIdDep,
) -> HealthResponse:
    result = HealthService(session=session, redis_client=redis_client).check()
    return HealthResponse(
        status=result.overall,
        service=settings.app_name,
        checks=HealthChecks(database=result.database, redis=result.redis),
        correlation_id=correlation_id,
    )
