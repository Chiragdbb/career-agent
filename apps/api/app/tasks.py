"""Enqueue helpers for background tasks (overridable in tests)."""

from __future__ import annotations

import uuid
from typing import Protocol


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
    """Run discovery synchronously (tests / local fallback without worker)."""

    def enqueue_discover_jobs(
        self,
        *,
        user_id: uuid.UUID,
        workflow_run_id: uuid.UUID,
        max_results: int,
    ) -> str:
        from workers.discovery.tasks import _run_discovery

        _run_discovery(user_id, workflow_run_id, max_results)
        return f"inline-{workflow_run_id}"
