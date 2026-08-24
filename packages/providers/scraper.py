"""ScraperProvider — web page extraction.

Product default target (not implemented here): self-hosted Firecrawl.
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


class ScraperProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError

    @abstractmethod
    def scrape(self, request: ScrapeRequest) -> ScrapeResponse:
        raise NotImplementedError


class MockScraperProvider(ScraperProvider):
    def __init__(
        self,
        *,
        markdown: str = "# Mock page\n\nScraped content.",
        title: str = "Mock page",
        fail_with: Exception | None = None,
        simulate_timeout: bool = False,
        latency_ms: float = 5.0,
    ) -> None:
        self._markdown = markdown
        self._title = title
        self._behavior = MockBehavior(
            fail_with=fail_with,
            simulate_timeout=simulate_timeout,
            latency_ms=latency_ms,
            provider_name="mock-scraper",
        )
        self._meta = ProviderMetadata(
            name="mock-scraper",
            vendor="mock",
            capabilities=frozenset({"scrape", "markdown"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def scrape(self, request: ScrapeRequest) -> ScrapeResponse:
        self._behavior.before_call(operation="scrape", timeout_seconds=request.timeout_seconds)
        return ScrapeResponse(
            url=request.url,
            title=self._title,
            markdown=self._markdown if "markdown" in request.formats else "",
            html="<html></html>" if "html" in request.formats else None,
            usage=self._behavior.usage(operation="scrape", unit_type="pages", units=1.0),
        )
