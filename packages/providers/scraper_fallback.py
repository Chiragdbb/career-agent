"""Scraper provider that tries multiple backends in order."""

from __future__ import annotations

import logging
import time

from packages.providers.base import ProviderMetadata, UsageInfo
from packages.providers.exceptions import ProviderError
from packages.providers.scraper import (
    CrawlRequest,
    CrawlResponse,
    ScrapeRequest,
    ScrapeResponse,
    ScrapedPage,
    ScraperProvider,
)

logger = logging.getLogger("career.fetch")


class FallbackScraperProvider(ScraperProvider):
    """Try scrapers in order until one succeeds."""

    def __init__(self, providers: list[ScraperProvider]) -> None:
        if not providers:
            raise ValueError("FallbackScraperProvider requires at least one provider")
        self._providers = providers
        names = [p.metadata.name for p in providers]
        self._meta = ProviderMetadata(
            name="fallback-scraper",
            vendor="composite",
            capabilities=frozenset({"scrape", "crawl", "markdown"}),
            extra={"backends": names},
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
                provider=self._meta.name,
                extra={"backend": page.metadata.get("scraper_backend")},
            ),
        )

    def scrape_url(self, request: ScrapeRequest) -> ScrapedPage:
        errors: list[str] = []
        for provider in self._providers:
            name = provider.metadata.name
            try:
                page = provider.scrape_url(request)
                if (page.markdown or page.title or "").strip():
                    metadata = dict(page.metadata)
                    metadata["scraper_backend"] = name
                    return ScrapedPage(
                        url=page.url,
                        title=page.title,
                        markdown=page.markdown,
                        html=page.html,
                        links=page.links,
                        metadata=metadata,
                    )
                errors.append(f"{name}: empty content")
            except Exception as exc:
                errors.append(f"{name}: {exc}")
                logger.warning(
                    "SCRAPE_BACKEND_FAILED backend=%s url=%s error=%s",
                    name,
                    request.url,
                    exc,
                )
        raise ProviderError(
            f"All scrapers failed for {request.url}: {'; '.join(errors)}",
            provider=self._meta.name,
            operation="scrape_url",
        )

    def crawl_site(self, request: CrawlRequest) -> CrawlResponse:
        errors: list[str] = []
        for provider in self._providers:
            try:
                return provider.crawl_site(request)
            except Exception as exc:
                errors.append(f"{provider.metadata.name}: {exc}")
        raise ProviderError(
            f"All scrapers failed crawl for {request.url}: {'; '.join(errors)}",
            provider=self._meta.name,
            operation="crawl_site",
        )
