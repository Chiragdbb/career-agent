"""SearchProvider — web search.

Product default target (not implemented here): Tavily.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from pydantic import BaseModel, Field, HttpUrl

from packages.providers.base import (
    MockBehavior,
    ProviderMetadata,
    TimeoutMixin,
    UsageInfo,
)


class SearchRequest(TimeoutMixin):
    query: str = Field(min_length=1)
    max_results: int = Field(default=5, ge=1, le=50)
    include_domains: list[str] = Field(default_factory=list)
    exclude_domains: list[str] = Field(default_factory=list)


class SearchHit(BaseModel):
    title: str
    url: HttpUrl | str
    snippet: str = ""
    score: float | None = None


class SearchResponse(BaseModel):
    results: list[SearchHit]
    usage: UsageInfo


class SearchProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError

    @abstractmethod
    def search(self, request: SearchRequest) -> SearchResponse:
        raise NotImplementedError


class MockSearchProvider(SearchProvider):
    def __init__(
        self,
        *,
        results: list[SearchHit] | None = None,
        fail_with: Exception | None = None,
        simulate_timeout: bool = False,
        latency_ms: float = 1.0,
    ) -> None:
        self._results = results
        self._behavior = MockBehavior(
            fail_with=fail_with,
            simulate_timeout=simulate_timeout,
            latency_ms=latency_ms,
            provider_name="mock-search",
        )
        self._meta = ProviderMetadata(
            name="mock-search",
            vendor="mock",
            capabilities=frozenset({"web_search"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def search(self, request: SearchRequest) -> SearchResponse:
        self._behavior.before_call(operation="search", timeout_seconds=request.timeout_seconds)
        if self._results is not None:
            hits = self._results[: request.max_results]
        else:
            slug = re.sub(r"[^a-z0-9]+", "-", request.query.lower()).strip("-")[:48] or "job"
            hits = [
                SearchHit(
                    title=f"{request.query.title()}",
                    url=f"https://jobs.example.com/mock/{slug}",
                    snippet=f"Mock listing for: {request.query}",
                    score=1.0,
                )
            ]
        return SearchResponse(
            results=hits,
            usage=self._behavior.usage(operation="search", unit_type="searches", units=1.0),
        )
