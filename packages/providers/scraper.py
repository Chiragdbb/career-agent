"""ScraperProvider — web page extraction.

Product default: self-hosted Firecrawl via `FirecrawlScraperProvider`.
Scraped content is untrusted input.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field, HttpUrl

from packages.providers.base import (
    MockBehavior,
    ProviderMetadata,
    TimeoutMixin,
    UsageInfo,
)


class ScrapedPage(BaseModel):
    """Normalized page content (untrusted)."""

    url: HttpUrl | str
    title: str | None = None
    markdown: str = ""
    html: str | None = None
    links: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class ScrapeRequest(TimeoutMixin):
    url: HttpUrl | str
    formats: list[str] = Field(default_factory=lambda: ["markdown"])
    only_main_content: bool = True


class ScrapeResponse(BaseModel):
    url: HttpUrl | str
    title: str | None = None
    markdown: str = ""
    html: str | None = None
    links: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    usage: UsageInfo


class CrawlRequest(TimeoutMixin):
    url: HttpUrl | str
    limit: int = Field(default=10, ge=1, le=100)
    formats: list[str] = Field(default_factory=lambda: ["markdown"])
    only_main_content: bool = True


class CrawlResponse(BaseModel):
    root_url: HttpUrl | str
    pages: list[ScrapedPage]
    usage: UsageInfo


class ScraperProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError

    @abstractmethod
    def scrape(self, request: ScrapeRequest) -> ScrapeResponse:
        raise NotImplementedError

    def scrape_url(self, request: ScrapeRequest) -> ScrapedPage:
        """Default: wrap scrape() into ScrapedPage."""
        response = self.scrape(request)
        return ScrapedPage(
            url=response.url,
            title=response.title,
            markdown=response.markdown,
            html=response.html,
            links=response.links,
            metadata=response.metadata,
        )

    def crawl_site(self, request: CrawlRequest) -> CrawlResponse:
        """Default: scrape the root URL only."""
        page = self.scrape_url(
            ScrapeRequest(
                url=request.url,
                formats=request.formats,
                only_main_content=request.only_main_content,
                timeout_seconds=request.timeout_seconds,
            )
        )
        return CrawlResponse(
            root_url=request.url,
            pages=[page],
            usage=UsageInfo(
                operation="crawl_site",
                unit_type="pages",
                units=1.0,
                provider=self.metadata.name,
            ),
        )


class MockScraperProvider(ScraperProvider):
    def __init__(
        self,
        *,
        markdown: str = "# Mock page\n\nScraped content.",
        title: str = "Mock page",
        pages: list[ScrapedPage] | None = None,
        fail_with: Exception | None = None,
        simulate_timeout: bool = False,
        latency_ms: float = 5.0,
    ) -> None:
        self._markdown = markdown
        self._title = title
        self._pages = pages
        self._behavior = MockBehavior(
            fail_with=fail_with,
            simulate_timeout=simulate_timeout,
            latency_ms=latency_ms,
            provider_name="mock-scraper",
        )
        self._meta = ProviderMetadata(
            name="mock-scraper",
            vendor="mock",
            capabilities=frozenset({"scrape", "crawl", "markdown"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def scrape(self, request: ScrapeRequest) -> ScrapeResponse:
        self._behavior.before_call(operation="scrape", timeout_seconds=request.timeout_seconds)
        if self._pages:
            for page in self._pages:
                if str(page.url) == str(request.url):
                    return ScrapeResponse(
                        url=page.url,
                        title=page.title,
                        markdown=page.markdown if "markdown" in request.formats else "",
                        html=page.html if "html" in request.formats else None,
                        links=page.links,
                        metadata=page.metadata,
                        usage=self._behavior.usage(operation="scrape", unit_type="pages", units=1.0),
                    )
        return ScrapeResponse(
            url=request.url,
            title=self._title,
            markdown=self._markdown if "markdown" in request.formats else "",
            html="<html></html>" if "html" in request.formats else None,
            usage=self._behavior.usage(operation="scrape", unit_type="pages", units=1.0),
        )

    def crawl_site(self, request: CrawlRequest) -> CrawlResponse:
        self._behavior.before_call(operation="crawl_site", timeout_seconds=request.timeout_seconds)
        pages = (
            self._pages[: request.limit]
            if self._pages
            else [ScrapedPage(url=request.url, title=self._title, markdown=self._markdown)]
        )
        return CrawlResponse(
            root_url=request.url,
            pages=pages,
            usage=self._behavior.usage(
                operation="crawl_site",
                unit_type="pages",
                units=float(len(pages)),
            ),
        )
