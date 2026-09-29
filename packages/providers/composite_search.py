"""Composite SearchProvider — Serper → Tavily with deduped URL merge."""

from __future__ import annotations

import logging
import time
from typing import Callable

from packages.providers.base import ProviderMetadata, UsageInfo
from packages.providers.exceptions import ProviderError
from packages.providers.search import SearchHit, SearchProvider, SearchRequest, SearchResponse

logger = logging.getLogger("career.search.composite")


def _normalize_url(url: str) -> str:
    return url.strip().rstrip("/").lower()


def wrap_search_with_usage_logging(
    search: SearchProvider,
    *,
    usage: object,
    context: object,
) -> SearchProvider:
    """Wrap any search provider so composite attempts log to provider_usage."""

    from packages.providers.base import UsageInfo

    def on_attempt(
        *,
        provider_name: str,
        operation: str,
        success: bool,
        error: str | None = None,
        extra: dict | None = None,
    ) -> None:
        usage.record(
            context=context,
            provider_name=provider_name,
            operation=operation,
            usage=UsageInfo(
                operation=operation,
                unit_type="searches",
                units=1.0,
                provider=provider_name,
                extra=extra or {},
            ),
            success=success,
            error=error,
            related_entity_type="workflow_run",
            related_entity_id=context.workflow_run_id,
        )

    if isinstance(search, CompositeSearchProvider):
        return CompositeSearchProvider(search.providers, on_attempt=on_attempt)
    return CompositeSearchProvider([search], on_attempt=on_attempt)


class CompositeSearchProvider(SearchProvider):
    """Try providers in order; merge results; log each attempt via callback."""

    def __init__(
        self,
        providers: list[SearchProvider],
        *,
        on_attempt: Callable[..., None] | None = None,
    ) -> None:
        if not providers:
            raise ValueError("CompositeSearchProvider requires at least one provider")
        self._providers = providers
        self._on_attempt = on_attempt
        names = "+".join(p.metadata.name for p in providers)
        self._meta = ProviderMetadata(
            name=f"composite-search({names})",
            vendor="composite",
            capabilities=frozenset({"web_search"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    @property
    def providers(self) -> list[SearchProvider]:
        return list(self._providers)

    def search(self, request: SearchRequest) -> SearchResponse:
        started = time.perf_counter()
        merged: list[SearchHit] = []
        seen: set[str] = set()
        total_units = 0.0
        last_provider = self._providers[0].metadata.name

        for provider in self._providers:
            last_provider = provider.metadata.name
            attempt_started = time.perf_counter()
            try:
                response = provider.search(request)
                total_units += float(response.usage.units or 1.0)
                for hit in response.results:
                    key = _normalize_url(str(hit.url))
                    if key in seen:
                        continue
                    seen.add(key)
                    merged.append(hit)
                    if len(merged) >= request.max_results:
                        break
                self._emit_attempt(
                    provider=provider.metadata.name,
                    success=True,
                    result_count=len(response.results),
                    latency_ms=(time.perf_counter() - attempt_started) * 1000.0,
                )
                if len(merged) >= request.max_results:
                    break
            except ProviderError as exc:
                self._emit_attempt(
                    provider=provider.metadata.name,
                    success=False,
                    error=str(exc),
                    latency_ms=(time.perf_counter() - attempt_started) * 1000.0,
                )
                logger.warning("search_provider_failed provider=%s error=%s", provider.metadata.name, exc)
                continue
            except Exception as exc:
                self._emit_attempt(
                    provider=provider.metadata.name,
                    success=False,
                    error=str(exc),
                    latency_ms=(time.perf_counter() - attempt_started) * 1000.0,
                )
                logger.warning("search_provider_failed provider=%s error=%s", provider.metadata.name, exc)
                continue

        latency_ms = (time.perf_counter() - started) * 1000.0
        return SearchResponse(
            results=merged[: request.max_results],
            usage=UsageInfo(
                operation="search",
                unit_type="searches",
                units=max(total_units, 1.0),
                latency_ms=latency_ms,
                provider=self._meta.name,
                extra={
                    "result_count": len(merged),
                    "providers_tried": [p.metadata.name for p in self._providers],
                    "last_provider": last_provider,
                },
            ),
        )

    def _emit_attempt(
        self,
        *,
        provider: str,
        success: bool,
        result_count: int = 0,
        error: str | None = None,
        latency_ms: float = 0.0,
    ) -> None:
        if self._on_attempt is None:
            return
        self._on_attempt(
            provider_name=provider,
            operation="search",
            success=success,
            error=error,
            extra={"result_count": result_count, "latency_ms": latency_ms},
        )
