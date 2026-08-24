"""Shared provider metadata, usage tracking, and timeout defaults."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from packages.providers.exceptions import ProviderError, ProviderTimeoutError

# Default wall-clock timeout for provider operations (seconds).
# Adapters must honor `timeout_seconds` on each request (e.g. httpx timeout /
# asyncio.wait_for). Mocks raise ProviderTimeoutError when simulate_timeout=True.
DEFAULT_TIMEOUT_SECONDS = 30.0


class ProviderMetadata(BaseModel):
    """Describes a concrete provider adapter instance."""

    name: str
    vendor: str
    version: str = "0.1.0"
    capabilities: frozenset[str] = Field(default_factory=frozenset)


class UsageInfo(BaseModel):
    """Normalized usage / cost signal returned with every provider response."""

    operation: str
    unit_type: str = "requests"
    units: float = 1.0
    estimated_cost_usd: float | None = None
    latency_ms: float | None = None
    provider: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class TimeoutMixin(BaseModel):
    """Request fields shared by all provider operations."""

    timeout_seconds: float = Field(
        default=DEFAULT_TIMEOUT_SECONDS,
        gt=0,
        description="Maximum wall-clock time for this operation.",
    )


class MockBehavior:
    """Configurable failure / timeout behavior for mock adapters."""

    def __init__(
        self,
        *,
        fail_with: Exception | None = None,
        simulate_timeout: bool = False,
        latency_ms: float = 1.0,
        provider_name: str = "mock",
    ) -> None:
        self.fail_with = fail_with
        self.simulate_timeout = simulate_timeout
        self.latency_ms = latency_ms
        self.provider_name = provider_name

    def before_call(self, *, operation: str, timeout_seconds: float) -> None:
        if timeout_seconds <= 0:
            raise ProviderError(
                "timeout_seconds must be positive",
                provider=self.provider_name,
                operation=operation,
            )
        if self.simulate_timeout:
            raise ProviderTimeoutError(
                f"{self.provider_name} timed out after {timeout_seconds}s",
                provider=self.provider_name,
                operation=operation,
            )
        if self.fail_with is not None:
            raise self.fail_with

    def usage(
        self,
        *,
        operation: str,
        unit_type: str = "requests",
        units: float = 1.0,
        estimated_cost_usd: float | None = 0.0,
        extra: dict[str, Any] | None = None,
    ) -> UsageInfo:
        return UsageInfo(
            operation=operation,
            unit_type=unit_type,
            units=units,
            estimated_cost_usd=estimated_cost_usd,
            latency_ms=self.latency_ms,
            provider=self.provider_name,
            extra=extra or {},
        )
