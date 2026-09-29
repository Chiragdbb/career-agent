"""Serper SearchProvider adapter (Google SERP JSON)."""

from __future__ import annotations

import time
from typing import Any

from packages.providers.base import ProviderMetadata, UsageInfo
from packages.providers.exceptions import ProviderNotConfiguredError, ProviderValidationError
from packages.providers.http_utils import request_with_retries
from packages.providers.search import SearchHit, SearchProvider, SearchRequest, SearchResponse

_SERPER_URL = "https://google.serper.dev/search"


class SerperSearchProvider(SearchProvider):
    def __init__(
        self,
        *,
        api_key: str,
        max_retries: int = 3,
        default_timeout_seconds: float = 30.0,
    ) -> None:
        key = (api_key or "").strip()
        if not key:
            raise ProviderNotConfiguredError(
                "SERPER_API_KEY is required for SerperSearchProvider",
                provider="serper-search",
            )
        self._api_key = key
        self._max_retries = max_retries
        self._default_timeout = default_timeout_seconds
        self._meta = ProviderMetadata(
            name="serper-search",
            vendor="serper",
            capabilities=frozenset({"web_search"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def search(self, request: SearchRequest) -> SearchResponse:
        started = time.perf_counter()
        payload: dict[str, Any] = {
            "q": request.query,
            "num": min(request.max_results, 50),
        }
        if request.include_domains:
            site = " OR ".join(f"site:{d}" for d in request.include_domains[:5])
            payload["q"] = f"{request.query} ({site})"

        response = request_with_retries(
            method="POST",
            url=_SERPER_URL,
            provider="serper-search",
            operation="search",
            timeout_seconds=request.timeout_seconds or self._default_timeout,
            max_retries=self._max_retries,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-API-KEY": self._api_key,
            },
        )
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderValidationError(
                "Serper returned non-JSON response",
                provider="serper-search",
                operation="search",
            ) from exc

        organic = data.get("organic") or []
        if not isinstance(organic, list):
            organic = []

        hits: list[SearchHit] = []
        for item in organic[: request.max_results]:
            if not isinstance(item, dict):
                continue
            url = item.get("link")
            title = item.get("title") or ""
            if not url:
                continue
            hits.append(
                SearchHit(
                    title=str(title),
                    url=str(url),
                    snippet=str(item.get("snippet") or ""),
                    score=None,
                )
            )

        latency_ms = (time.perf_counter() - started) * 1000.0
        return SearchResponse(
            results=hits,
            usage=UsageInfo(
                operation="search",
                unit_type="searches",
                units=1.0,
                estimated_cost_usd=0.001,
                latency_ms=latency_ms,
                provider="serper-search",
                extra={"result_count": len(hits)},
            ),
        )
