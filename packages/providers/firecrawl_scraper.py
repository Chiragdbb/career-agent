"""Firecrawl ScraperProvider adapter (self-hosted via FIRECRAWL_BASE_URL).

Scraped content is untrusted input — callers must not treat it as instructions.
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
from packages.providers.scraper import (
    CrawlRequest,
    CrawlResponse,
    ScrapeRequest,
    ScrapeResponse,
    ScrapedPage,
    ScraperProvider,
)


class FirecrawlScraperProvider(ScraperProvider):
    """Talks to a self-hosted Firecrawl instance."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        max_retries: int = 3,
        default_timeout_seconds: float = 60.0,
    ) -> None:
        base = (base_url or "").strip().rstrip("/")
        if not base:
            raise ProviderNotConfiguredError(
                "FIRECRAWL_BASE_URL is required for FirecrawlScraperProvider",
                provider="firecrawl-scraper",
            )
        self._base_url = base
        self._api_key = (api_key or "").strip() or None
        self._max_retries = max_retries
        self._default_timeout = default_timeout_seconds
        self._meta = ProviderMetadata(
            name="firecrawl-scraper",
            vendor="firecrawl",
            capabilities=frozenset({"scrape", "crawl", "markdown"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def scrape(self, request: ScrapeRequest) -> ScrapeResponse:
        started = time.perf_counter()
        page = self.scrape_url(request)
        return ScrapeResponse(
            url=page.url,
            title=page.title,
            markdown=page.markdown,
            html=page.html,
            links=page.links,
            metadata=page.metadata,
            usage=UsageInfo(
                operation="scrape",
                unit_type="pages",
                units=1.0,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                provider="firecrawl-scraper",
            ),
        )

    def scrape_url(self, request: ScrapeRequest) -> ScrapedPage:
        payload = {
            "url": str(request.url),
            "formats": request.formats,
            "onlyMainContent": request.only_main_content,
        }
        data = self._post_json(
            "/v1/scrape",
            payload,
            operation="scrape_url",
            timeout_seconds=request.timeout_seconds or self._default_timeout,
        )
        return _normalize_page(data.get("data") or data, fallback_url=str(request.url))

    def crawl_site(self, request: CrawlRequest) -> CrawlResponse:
        started = time.perf_counter()
        payload = {
            "url": str(request.url),
            "limit": request.limit,
            "scrapeOptions": {
                "formats": request.formats,
                "onlyMainContent": request.only_main_content,
            },
        }
        data = self._post_json(
            "/v1/crawl",
            payload,
            operation="crawl_site",
            timeout_seconds=request.timeout_seconds or self._default_timeout,
        )
        pages_raw = data.get("data") or data.get("pages") or []
        if isinstance(pages_raw, dict):
            pages_raw = pages_raw.get("data") or []
        if not isinstance(pages_raw, list):
            raise ProviderValidationError(
                "Firecrawl crawl response missing pages list",
                provider="firecrawl-scraper",
                operation="crawl_site",
            )
        pages = [
            _normalize_page(item, fallback_url=str(request.url))
            for item in pages_raw
            if isinstance(item, dict)
        ]
        return CrawlResponse(
            root_url=request.url,
            pages=pages,
            usage=UsageInfo(
                operation="crawl_site",
                unit_type="pages",
                units=float(len(pages)),
                latency_ms=(time.perf_counter() - started) * 1000.0,
                provider="firecrawl-scraper",
            ),
        )

    def _post_json(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        operation: str,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        response = request_with_retries(
            method="POST",
            url=f"{self._base_url}{path}",
            provider="firecrawl-scraper",
            operation=operation,
            timeout_seconds=timeout_seconds,
            max_retries=self._max_retries,
            json=payload,
            headers=headers,
        )
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderValidationError(
                "Firecrawl returned non-JSON response",
                provider="firecrawl-scraper",
                operation=operation,
            ) from exc
        if not isinstance(data, dict):
            raise ProviderValidationError(
                "Firecrawl returned unexpected JSON shape",
                provider="firecrawl-scraper",
                operation=operation,
            )
        return data


def _normalize_page(raw: dict[str, Any], *, fallback_url: str) -> ScrapedPage:
    meta_raw = raw.get("metadata") or {}
    metadata: dict[str, str] = {}
    if isinstance(meta_raw, dict):
        for key, value in meta_raw.items():
            if value is None:
                continue
            metadata[str(key)] = str(value)

    title = raw.get("title") or metadata.get("title")
    links = raw.get("links") or []
    if not isinstance(links, list):
        links = []
    return ScrapedPage(
        url=str(raw.get("url") or metadata.get("sourceURL") or fallback_url),
        title=str(title) if title else None,
        markdown=str(raw.get("markdown") or ""),
        html=str(raw["html"]) if raw.get("html") is not None else None,
        links=[str(link) for link in links],
        metadata=metadata,
    )
