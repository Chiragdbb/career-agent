"""Tavily SearchProvider adapter.

Normalizes Tavily responses into SearchHit / SearchResponse.
Tavily-specific payloads never leave this module.
"""

from __future__ import annotations

import time
from typing import Any

from packages.providers.base import ProviderMetadata, UsageInfo
from packages.providers.exceptions import (
    ProviderNotConfiguredError,
    ProviderValidationError,
)
from packages.providers.http_utils import request_with_retries
from packages.providers.search import (
    SearchHit,
    SearchProvider,
    SearchRequest,
    SearchResponse,
)

_TAVILY_SEARCH_URL = "https://api.tavily.com/search"


class TavilySearchProvider(SearchProvider):
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
                "TAVILY_API_KEY is required for TavilySearchProvider",
                provider="tavily-search",
            )
        self._api_key = key
        self._max_retries = max_retries
        self._default_timeout = default_timeout_seconds
        self._meta = ProviderMetadata(
            name="tavily-search",
            vendor="tavily",
            capabilities=frozenset({"web_search"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def search(self, request: SearchRequest) -> SearchResponse:
        started = time.perf_counter()
        payload: dict[str, Any] = {
            "api_key": self._api_key,
            "query": request.query,
            "max_results": request.max_results,
            "include_domains": request.include_domains or None,
            "exclude_domains": request.exclude_domains or None,
            "search_depth": "basic",
        }
        # Drop None values so Tavily does not reject empty lists oddly.
        payload = {k: v for k, v in payload.items() if v is not None}

        response = request_with_retries(
            method="POST",
            url=_TAVILY_SEARCH_URL,
            provider="tavily-search",
            operation="search",
            timeout_seconds=request.timeout_seconds or self._default_timeout,
            max_retries=self._max_retries,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderValidationError(
                "Tavily returned non-JSON response",
                provider="tavily-search",
                operation="search",
            ) from exc

        raw_results = data.get("results") or []
        if not isinstance(raw_results, list):
            raise ProviderValidationError(
                "Tavily results payload was not a list",
                provider="tavily-search",
                operation="search",
            )

        hits: list[SearchHit] = []
        for item in raw_results[: request.max_results]:
            if not isinstance(item, dict):
                continue
            url = item.get("url") or item.get("link")
            title = item.get("title") or ""
            if not url:
                continue
            score = item.get("score")
            try:
                score_f = float(score) if score is not None else None
            except (TypeError, ValueError):
                score_f = None
            hits.append(
                SearchHit(
                    title=str(title),
                    url=str(url),
                    snippet=str(item.get("content") or item.get("snippet") or ""),
                    score=score_f,
                )
            )

        latency_ms = (time.perf_counter() - started) * 1000.0
        return SearchResponse(
            results=hits,
            usage=UsageInfo(
                operation="search",
                unit_type="searches",
                units=1.0,
                estimated_cost_usd=None,
                latency_ms=latency_ms,
                provider="tavily-search",
                extra={"result_count": len(hits)},
            ),
        )
