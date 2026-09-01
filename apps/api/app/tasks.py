"""Enqueue helpers for background tasks (overridable in tests)."""

from __future__ import annotations

import logging
import threading
import uuid
from typing import Protocol

logger = logging.getLogger(__name__)


class DiscoveryTaskClient(Protocol):
    def enqueue_discover_jobs(
        self,
        *,
        user_id: uuid.UUID,
        workflow_run_id: uuid.UUID,
        max_results: int,
    ) -> str: ...


class CeleryDiscoveryTaskClient:
    def enqueue_discover_jobs(
        self,
        *,
        user_id: uuid.UUID,
        workflow_run_id: uuid.UUID,
        max_results: int,
    ) -> str:
        from workers.discovery.tasks import discover_jobs

        async_result = discover_jobs.delay(
            str(user_id),
            str(workflow_run_id),
            max_results,
        )
        return async_result.id


class InlineDiscoveryTaskClient:
    """Run discovery in a background thread (tests / local fallback without worker)."""

    def enqueue_discover_jobs(
        self,
        *,
        user_id: uuid.UUID,
        workflow_run_id: uuid.UUID,
        max_results: int,
    ) -> str:
        from workers.discovery.tasks import _run_discovery

        task_id = f"inline-{workflow_run_id}"

        def _run() -> None:
            try:
                _run_discovery(user_id, workflow_run_id, max_results)
            except Exception:
                logger.exception(
                    "inline discovery failed user=%s run=%s", user_id, workflow_run_id
                )

        thread = threading.Thread(target=_run, daemon=True, name=f"discovery-{workflow_run_id}")
        thread.start()
        return task_id
