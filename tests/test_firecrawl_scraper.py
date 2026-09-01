"""STEP 11 — FirecrawlScraperProvider (mocked HTTP; no live Firecrawl)."""

from __future__ import annotations

import json

import pytest

from packages.providers.exceptions import ProviderNotConfiguredError
from packages.providers.firecrawl_scraper import FirecrawlScraperProvider
from packages.providers.scraper import CrawlRequest, ScrapeRequest, ScrapedPage


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.headers = {}
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def test_firecrawl_requires_base_url() -> None:
    with pytest.raises(ProviderNotConfiguredError):
        FirecrawlScraperProvider(base_url="")


def test_firecrawl_scrape_url_normalizes(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_request(**kwargs):
        captured.update(kwargs.get("json") or {})
        assert kwargs["url"].endswith("/v1/scrape")
        return _FakeResponse(
            200,
            {
                "data": {
                    "url": "https://example.com/jobs/1",
                    "markdown": "# Role\n\nUntrusted page content",
                    "metadata": {"title": "Role"},
                    "links": ["https://example.com"],
                }
            },
        )

    monkeypatch.setattr(
        "packages.providers.firecrawl_scraper.request_with_retries",
        fake_request,
    )
    provider = FirecrawlScraperProvider(base_url="http://localhost:3002")
    page = provider.scrape_url(ScrapeRequest(url="https://example.com/jobs/1"))
    assert isinstance(page, ScrapedPage)
    assert captured.get("onlyMainContent") is True
    assert page.title == "Role"
    assert "Untrusted" in page.markdown
    assert page.links == ["https://example.com"]


def test_firecrawl_crawl_site(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_request(**kwargs):
        assert kwargs["url"].endswith("/v1/crawl")
        return _FakeResponse(
            200,
            {
                "data": [
                    {
                        "url": "https://example.com/jobs/1",
                        "markdown": "Job 1",
                        "metadata": {"title": "Job 1"},
                    },
                    {
                        "url": "https://example.com/jobs/2",
                        "markdown": "Job 2",
                        "metadata": {"title": "Job 2"},
                    },
                ]
            },
        )

    monkeypatch.setattr(
        "packages.providers.firecrawl_scraper.request_with_retries",
        fake_request,
    )
    provider = FirecrawlScraperProvider(base_url="http://localhost:3002", api_key="fc-test")
    response = provider.crawl_site(CrawlRequest(url="https://example.com/careers", limit=10))
    assert len(response.pages) == 2
    assert response.usage.units == 2.0
    assert response.usage.provider == "firecrawl-scraper"
