"""Per-user Redis lock for job discovery runs."""

from __future__ import annotations

import uuid
from typing import Any, Protocol

# TTL is the crash-recovery mechanism when release() is never called (worker crash, etc.).
DEFAULT_DISCOVERY_LOCK_TTL_SECONDS = 900  # 15 minutes


def discovery_lock_key(user_id: uuid.UUID) -> str:
    return f"career-agent:discovery_lock:{user_id}"


class LockStore(Protocol):
    def set(self, name: str, value: str, nx: bool = False, ex: int | None = None) -> Any: ...

    def get(self, name: str) -> str | None: ...

    def delete(self, name: str) -> Any: ...


class DiscoveryLock:
    """One active discovery run per user at a time."""

    def __init__(
        self,
        redis_client: LockStore | None = None,
        *,
        ttl_seconds: int = DEFAULT_DISCOVERY_LOCK_TTL_SECONDS,
    ) -> None:
        self._redis = redis_client
        self._ttl_seconds = ttl_seconds

    def acquire(self, user_id: uuid.UUID, run_id: uuid.UUID) -> bool:
        if self._redis is None:
            return True
        return bool(
            self._redis.set(
                discovery_lock_key(user_id),
                str(run_id),
                nx=True,
                ex=self._ttl_seconds,
            )
        )

    def release(self, user_id: uuid.UUID) -> None:
        if self._redis is None:
            return
        self._redis.delete(discovery_lock_key(user_id))

    def get_holder(self, user_id: uuid.UUID) -> uuid.UUID | None:
        if self._redis is None:
            return None
        raw = self._redis.get(discovery_lock_key(user_id))
        if not raw:
            return None
        try:
            return uuid.UUID(str(raw))
        except ValueError:
            return None
