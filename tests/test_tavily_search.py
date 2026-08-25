"""STEP 10 — TavilySearchProvider (mocked HTTP)."""

from __future__ import annotations

import json

import pytest

from packages.providers.exceptions import (
    ProviderNotConfiguredError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from packages.providers.search import SearchHit, SearchRequest
from packages.providers.tavily_search import TavilySearchProvider


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | str, headers: dict | None = None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = payload if isinstance(payload, str) else json.dumps(payload)

    def json(self):
        if isinstance(self._payload, str):
            raise ValueError("not json")
        return self._payload


def test_tavily_requires_api_key() -> None:
    with pytest.raises(ProviderNotConfiguredError):
        TavilySearchProvider(api_key="")


def test_tavily_normalizes_results(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_request(**kwargs):
        captured.update(kwargs)
        return _FakeResponse(
            200,
            {
                "results": [
                    {
                        "title": "Backend Engineer",
                        "url": "https://jobs.example.com/1",
                        "content": "Build APIs",
                        "score": 0.91,
                    },
                    {"title": "Skip me", "content": "no url"},
                ]
            },
        )

    monkeypatch.setattr(
        "packages.providers.tavily_search.request_with_retries",
        fake_request,
    )
    provider = TavilySearchProvider(api_key="tvly-test")
    response = provider.search(SearchRequest(query="backend engineer", max_results=5))
    assert len(response.results) == 1
    hit = response.results[0]
    assert isinstance(hit, SearchHit)
    assert hit.title == "Backend Engineer"
    assert str(hit.url) == "https://jobs.example.com/1"
    assert hit.snippet == "Build APIs"
    assert hit.score == 0.91
    assert response.usage.provider == "tavily-search"
    assert captured["json"]["api_key"] == "tvly-test"
    # No Tavily-specific objects leaked on the response.
    assert set(response.model_dump().keys()) == {"results", "usage"}


def test_tavily_rate_limit_classified(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_request(**kwargs):
        raise ProviderRateLimitError("rate", provider="tavily-search", operation="search")

    monkeypatch.setattr(
        "packages.providers.tavily_search.request_with_retries",
        fake_request,
    )
    provider = TavilySearchProvider(api_key="tvly-test")
    with pytest.raises(ProviderRateLimitError):
        provider.search(SearchRequest(query="x"))


def test_tavily_timeout_classified(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_request(**kwargs):
        raise ProviderTimeoutError("timeout", provider="tavily-search", operation="search")

    monkeypatch.setattr(
        "packages.providers.tavily_search.request_with_retries",
        fake_request,
    )
    provider = TavilySearchProvider(api_key="tvly-test")
    with pytest.raises(ProviderTimeoutError):
        provider.search(SearchRequest(query="x"))
