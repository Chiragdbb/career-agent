"""Scrapling ScraperProvider — HTTP/browser fetch for job re-scrape and fallback scrape.

Scraped content is untrusted input. URLs are validated before outbound fetch (SSRF-safe).
"""

from __future__ import annotations

import logging
import time
from typing import Any, Literal

from packages.providers.base import ProviderMetadata, UsageInfo
from packages.providers.exceptions import (
    ProviderError,
    ProviderNotConfiguredError,
    ProviderValidationError,
)
from packages.providers.scraper import ScrapeRequest, ScrapeResponse, ScrapedPage, ScraperProvider
from packages.shared.security import SecurityError, validate_public_url

logger = logging.getLogger("career.scrapling")

FetcherMode = Literal["http", "dynamic", "stealthy"]


def _pick_css_text(response: Any, selector_list: str | None) -> str | None:
    if not selector_list:
        return None
    for selector in selector_list.split(","):
        sel = selector.strip()
        if not sel:
            continue
        try:
            nodes = response.css(sel)
            if not nodes:
                continue
            node = nodes[0]
            text_fn = getattr(node, "get_all_text", None)
            text = (text_fn() if callable(text_fn) else str(node)).strip()
            if text:
                return text
        except Exception:
            continue
    return None


def _job_board_markdown(url: str, response: Any) -> str | None:
    from packages.providers.playwright_jobs import match_job_source

    source = match_job_source(url)
    if source is None:
        return None
    title = _pick_css_text(response, source.title)
    description = _pick_css_text(response, source.description)
    if not title or not description:
        return None
    location = _pick_css_text(response, source.location)
    lines = [f"# {title}", ""]
    if location:
        lines.extend([f"**Location:** {location}", ""])
    lines.append(description.strip())
    return "\n".join(lines)


def _page_markdown(response: Any, *, url: str) -> tuple[str, str | None]:
    board_md = _job_board_markdown(url, response)
    if board_md:
        title = _pick_css_text(response, "title, h1")
        return board_md, title

    title = _pick_css_text(response, "title") or _pick_css_text(response, "h1")
    markdown = ""
    markdown_fn = getattr(response, "markdown", None)
    if callable(markdown_fn):
        try:
            markdown = (markdown_fn() or "").strip()
        except ModuleNotFoundError:
            logger.info("scrapling_markdownify_missing using plain text fallback url=%s", url)
        except Exception as exc:
            logger.warning("scrapling_markdown_failed url=%s error=%s", url, exc)

    if not markdown:
        text_fn = getattr(response, "get_all_text", None)
        body = (text_fn() if callable(text_fn) else "").strip()
        if title and body:
            markdown = f"# {title}\n\n{body}"
        else:
            markdown = body or title or ""

    return markdown, title


class ScraplingScraperProvider(ScraperProvider):
    """Fetch pages with Scrapling and normalize to ScrapedPage markdown."""

    def __init__(
        self,
        *,
        fetcher: FetcherMode = "http",
        adaptive: bool = False,
        headless: bool = True,
        default_timeout_seconds: float = 45.0,
    ) -> None:
        self._fetcher_mode = fetcher
        self._adaptive = adaptive
        self._headless = headless
        self._default_timeout = default_timeout_seconds
        self._configure_fetchers()
        self._meta = ProviderMetadata(
            name="scrapling-scraper",
            vendor="scrapling",
            capabilities=frozenset({"scrape", "markdown"}),
            extra={"fetcher": fetcher, "adaptive": str(adaptive).lower()},
        )

    def _configure_fetchers(self) -> None:
        try:
            from scrapling.fetchers import DynamicFetcher, Fetcher, StealthyFetcher
        except ImportError as exc:
            raise ProviderNotConfiguredError(
                'scrapling is not installed; pip install "scrapling[fetchers]"',
                provider="scrapling-scraper",
            ) from exc

        kwargs: dict[str, Any] = {}
        if self._adaptive:
            kwargs["adaptive"] = True
        for cls in (Fetcher, DynamicFetcher, StealthyFetcher):
            configure = getattr(cls, "configure", None)
            if callable(configure) and kwargs:
                configure(**kwargs)

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def scrape(self, request: ScrapeRequest) -> ScrapeResponse:
        started = time.perf_counter()
        page = self.scrape_url(request)
        return ScrapeResponse(
            url=page.url,
            title=page.title,
            markdown=page.markdown if "markdown" in request.formats else "",
            html=page.html if "html" in request.formats else None,
            links=page.links,
            metadata=page.metadata,
            usage=UsageInfo(
                operation="scrape",
                unit_type="pages",
                units=1.0,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                provider=self._meta.name,
                extra={"fetcher": self._fetcher_mode},
            ),
        )

    def scrape_url(self, request: ScrapeRequest) -> ScrapedPage:
        url = validate_public_url(str(request.url))
        timeout = request.timeout_seconds or self._default_timeout
        started = time.perf_counter()
        try:
            response = self._fetch(url, timeout_seconds=timeout)
        except SecurityError:
            raise
        except Exception as exc:
            raise ProviderError(
                f"Scrapling fetch failed for {url}: {exc}",
                provider=self._meta.name,
                operation="scrape_url",
            ) from exc

        status = int(getattr(response, "status", 0) or 0)
        if status >= 400:
            raise ProviderError(
                f"Scrapling HTTP {status} for {url}",
                provider=self._meta.name,
                operation="scrape_url",
            )

        markdown, title = _page_markdown(response, url=url)
        html_content = getattr(response, "html_content", None)
        html = html_content if isinstance(html_content, str) else None
        links: list[str] = []
        try:
            for node in response.css("a[href]"):
                href = node.attrib.get("href") if hasattr(node, "attrib") else None
                if href:
                    links.append(href)
        except Exception:
            pass

        latency = (time.perf_counter() - started) * 1000.0
        return ScrapedPage(
            url=url,
            title=title,
            markdown=markdown,
            html=html,
            links=links[:200],
            metadata={
                "scraper_backend": self._meta.name,
                "fetcher": self._fetcher_mode,
                "status": str(status),
                "latency_ms": f"{latency:.1f}",
            },
        )

    def _fetch(self, url: str, *, timeout_seconds: float) -> Any:
        timeout_ms = max(int(timeout_seconds * 1000), 1000)
        if self._fetcher_mode == "http":
            from scrapling.fetchers import Fetcher

            return Fetcher.get(url, timeout=timeout_ms)
        if self._fetcher_mode == "dynamic":
            from scrapling.fetchers import DynamicFetcher

            return DynamicFetcher.fetch(
                url,
                headless=self._headless,
                timeout=timeout_ms,
            )
        if self._fetcher_mode == "stealthy":
            from scrapling.fetchers import StealthyFetcher

            return StealthyFetcher.fetch(
                url,
                headless=self._headless,
                timeout=timeout_ms,
            )
        raise ProviderValidationError(
            f"Unknown SCRAPLING_FETCHER mode: {self._fetcher_mode}",
            provider=self._meta.name,
            operation="scrape_url",
        )


class EscalatingScraplingScraperProvider(ScraperProvider):
    """Try http → dynamic → stealthy on failure (cost-aware)."""

    _MODES: tuple[FetcherMode, ...] = ("http", "dynamic", "stealthy")

    def __init__(self, *, headless: bool = True, default_timeout_seconds: float = 45.0) -> None:
        self._headless = headless
        self._default_timeout = default_timeout_seconds
        self._meta = ProviderMetadata(
            name="escalating-scrapling-scraper",
            vendor="scrapling",
            capabilities=frozenset({"scrape", "markdown"}),
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
            markdown=page.markdown if "markdown" in request.formats else "",
            html=page.html if "html" in request.formats else None,
            links=page.links,
            metadata=page.metadata,
            usage=UsageInfo(
                operation="scrape",
                unit_type="pages",
                units=1.0,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                provider=self._meta.name,
                extra={"fetcher": page.metadata.get("fetcher_escalation", "http")},
            ),
        )

    def scrape_url(self, request: ScrapeRequest) -> ScrapedPage:
        last_exc: Exception | None = None
        for mode in self._MODES:
            backend = ScraplingScraperProvider(
                fetcher=mode,
                headless=self._headless,
                default_timeout_seconds=self._default_timeout,
            )
            try:
                page = backend.scrape_url(request)
                page.metadata["fetcher_escalation"] = mode
                return page
            except (ProviderError, ProviderValidationError) as exc:
                last_exc = exc
                logger.info("scrapling_escalate from=%s url=%s error=%s", mode, request.url, exc)
                continue
        if last_exc is not None:
            raise last_exc
        raise ProviderError("Scrapling escalation failed", provider=self._meta.name, operation="scrape_url")


class MockScraplingScraperProvider(ScraperProvider):
    """Deterministic Scrapling stand-in for tests."""

    def __init__(
        self,
        *,
        markdown: str = "# Mock Scrapling page\n\nJob description body.",
        title: str = "Mock Scrapling page",
    ) -> None:
        self._markdown = markdown
        self._title = title
        self._meta = ProviderMetadata(
            name="mock-scrapling-scraper",
            vendor="mock",
            capabilities=frozenset({"scrape", "markdown"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def scrape(self, request: ScrapeRequest) -> ScrapeResponse:
        page = self.scrape_url(request)
        return ScrapeResponse(
            url=page.url,
            title=page.title,
            markdown=page.markdown,
            usage=UsageInfo(
                operation="scrape",
                unit_type="pages",
                units=1.0,
                provider=self._meta.name,
            ),
        )

    def scrape_url(self, request: ScrapeRequest) -> ScrapedPage:
        return ScrapedPage(
            url=str(request.url),
            title=self._title,
            markdown=self._markdown,
            metadata={"scraper_backend": self._meta.name, "fetcher": "mock"},
        )
