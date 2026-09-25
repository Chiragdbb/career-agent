from __future__ import annotations

from fastapi import APIRouter

from app.config import Settings
from app.dependencies import CorrelationIdDep, DbSessionDep, RedisDep, SettingsDep
from app.schemas import HealthChecks, HealthResponse, LivenessResponse
from app.services.health import HealthService

router = APIRouter(tags=["health"])
liveness_router = APIRouter(tags=["health"])


def _liveness_payload(settings: Settings) -> LivenessResponse:
    return LivenessResponse(status="ok", service=settings.app_name)


@liveness_router.get("/", response_model=LivenessResponse, include_in_schema=False)
def root_liveness(settings: SettingsDep) -> LivenessResponse:
    """Render and other hosts probe HEAD/GET / during deploy."""
    return _liveness_payload(settings)


@liveness_router.get("/health", response_model=LivenessResponse)
def liveness(settings: SettingsDep) -> LivenessResponse:
    """Process liveness for load balancers. Does not check Postgres or Redis."""
    return _liveness_payload(settings)


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
