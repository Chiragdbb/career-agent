"""Persist provider call usage for cost and quota analytics."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from database.models.schema import ProviderUsage
from packages.providers.base import UsageInfo

logger = logging.getLogger("career.provider_usage")


@dataclass(frozen=True)
class ProviderUsageContext:
    user_id: uuid.UUID
    workflow_run_id: uuid.UUID | None = None
    workflow_task_id: uuid.UUID | None = None


class ProviderUsageService:
    """Write normalized provider usage rows (including Gemini RPM signals)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def record(
        self,
        *,
        context: ProviderUsageContext,
        provider_name: str,
        operation: str,
        usage: UsageInfo,
        success: bool = True,
        error: str | None = None,
    ) -> None:
        token_count: int | None = None
        if usage.unit_type == "tokens":
            token_count = int(usage.units)

        credit_count: float | None = None
        if usage.unit_type == "requests":
            credit_count = float(usage.units)

        payload = dict(usage.extra)
        payload["unit_type"] = usage.unit_type

        row = ProviderUsage(
            user_id=context.user_id,
            workflow_run_id=context.workflow_run_id,
            workflow_task_id=context.workflow_task_id,
            provider_name=provider_name,
            operation=operation,
            token_count=token_count,
            credit_count=credit_count,
            cost_estimate=usage.estimated_cost_usd,
            latency_ms=int(usage.latency_ms) if usage.latency_ms is not None else None,
            success=success,
            error=error,
            payload=payload,
        )
        self._session.add(row)
        try:
            self._session.flush()
        except Exception:
            logger.warning("provider_usage_record_failed", exc_info=True)
