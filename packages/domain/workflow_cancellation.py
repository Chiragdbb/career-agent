"""Cooperative workflow cancellation via Redis + database status."""

from __future__ import annotations

import uuid
from typing import Any, Protocol


def workflow_cancel_key(run_id: uuid.UUID) -> str:
    return f"career-agent:cancel:{run_id}"


class CancelStore(Protocol):
    def setex(self, name: str, time: int, value: str) -> Any: ...

    def get(self, name: str) -> str | None: ...

    def delete(self, name: str) -> Any: ...


class WorkflowCancellation:
    """Signal and query cancellation for long-running workflow runs."""

    def __init__(self, redis_client: CancelStore | None = None) -> None:
        self._redis = redis_client

    def request_cancel(self, run_id: uuid.UUID) -> None:
        if self._redis is None:
            return
        self._redis.setex(workflow_cancel_key(run_id), 3600, "1")

    def is_cancelled(self, run_id: uuid.UUID) -> bool:
        if self._redis is None:
            return False
        return bool(self._redis.get(workflow_cancel_key(run_id)))

    def clear(self, run_id: uuid.UUID) -> None:
        if self._redis is None:
            return
        self._redis.delete(workflow_cancel_key(run_id))
