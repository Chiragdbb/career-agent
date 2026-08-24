from __future__ import annotations

from dataclasses import dataclass

from redis import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class HealthCheckResult:
    database: str
    redis: str

    @property
    def overall(self) -> str:
        values = {self.database, self.redis}
        if values == {"ok"}:
            return "ok"
        if "unavailable" in values:
            return "unhealthy"
        return "degraded"


class HealthService:
    """Application-layer health checks (no business/domain logic)."""

    def __init__(self, session: Session, redis_client: Redis) -> None:
        self._session = session
        self._redis = redis_client

    def check(self) -> HealthCheckResult:
        return HealthCheckResult(
            database=self._check_database(),
            redis=self._check_redis(),
        )

    def _check_database(self) -> str:
        try:
            self._session.execute(text("SELECT 1"))
            return "ok"
        except Exception:
            return "unavailable"

    def _check_redis(self) -> str:
        try:
            if self._redis.ping():
                return "ok"
            return "unavailable"
        except Exception:
            return "unavailable"
