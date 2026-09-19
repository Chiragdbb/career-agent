"""Adapter-layer usage logging wrapper — one provider_usage row per attempt."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from typing import TypeVar

from packages.domain.provider_usage import ProviderUsageContext, ProviderUsageService
from packages.providers.base import UsageInfo

T = TypeVar("T")


def call_with_usage_log(
    usage: ProviderUsageService,
    *,
    context: ProviderUsageContext,
    provider: str,
    operation: str,
    fn: Callable[[], T],
    related_entity_type: str | None = None,
    related_entity_id: uuid.UUID | None = None,
    usage_from_result: Callable[[T], UsageInfo] | None = None,
) -> T:
    """Wrap any provider adapter call; logs success and failure attempts."""
    started = time.perf_counter()
    try:
        result = fn()
        info = (
            usage_from_result(result)
            if usage_from_result is not None
            else UsageInfo(
                operation=operation,
                unit_type="requests",
                units=1.0,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                provider=provider,
            )
        )
        if info.latency_ms is None:
            info = info.model_copy(
                update={"latency_ms": (time.perf_counter() - started) * 1000.0}
            )
        usage.record(
            context=context,
            provider_name=provider,
            operation=operation,
            usage=info,
            success=True,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )
        return result
    except Exception as exc:
        usage.record(
            context=context,
            provider_name=provider,
            operation=operation,
            usage=UsageInfo(
                operation=operation,
                unit_type="requests",
                units=1.0,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                provider=provider,
            ),
            success=False,
            error=str(exc)[:500],
            error_code=type(exc).__name__,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )
        raise
