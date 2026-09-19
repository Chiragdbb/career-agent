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

    def extract_structured_job(
        self,
        url: str,
        *,
        timeout_seconds: float | None = None,
    ) -> tuple[dict[str, Any], UsageInfo]:
        """One-off structured job extract — reserved for unknown boards (not known Playwright sources).

        Returns a dict matching StructuredJobPosting fields (no raw HTML).
        """
        from packages.providers.playwright_jobs import is_known_job_board

        if is_known_job_board(url):
            raise ProviderValidationError(
                "Firecrawl job extract is reserved for one-off company pages; "
                "known job boards must use Playwright",
                provider="firecrawl-scraper",
                operation="job_extraction",
            )

        started = time.perf_counter()
        schema = _job_posting_extract_schema()
        payload = {
            "url": str(url),
            "formats": ["extract"],
            "onlyMainContent": True,
            "extract": {
                "schema": schema,
                "prompt": (
                    "Extract a single job posting. Return only the fields in the schema. "
                    "description must be cleaned body prose only — no nav, footer, or scripts. "
                    "Do not invent salary or skills."
                ),
            },
        }
        data = self._post_json(
            "/v1/scrape",
            payload,
            operation="job_extraction",
            timeout_seconds=timeout_seconds or self._default_timeout,
        )
        page = data.get("data") or data
        extracted = {}
        if isinstance(page, dict):
            extracted = page.get("extract") or page.get("llm_extraction") or page.get("json") or {}
        if not isinstance(extracted, dict):
            raise ProviderValidationError(
                "Firecrawl structured extract missing job object",
                provider="firecrawl-scraper",
                operation="job_extraction",
            )
        # Never leak raw HTML into the returned payload.
        cleaned = {k: v for k, v in extracted.items() if k != "html" and k != "rawHtml"}
        cleaned.setdefault("source", "firecrawl")
        cleaned.setdefault("application_url", str(url))
        cleaned.setdefault("scraped_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        usage = UsageInfo(
            operation="job_extraction",
            unit_type="credits",
            units=1.0,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            provider="firecrawl-scraper",
            estimated_cost_usd=None,
            extra={"mode": "one_off_structured"},
        )
        return cleaned, usage

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


def _job_posting_extract_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "external_job_id": {"type": "string"},
            "company_name": {"type": "string"},
            "company_domain": {"type": ["string", "null"]},
            "title": {"type": "string"},
            "description": {"type": "string"},
            "requirements": {"type": "array", "items": {"type": "string"}},
            "skills": {"type": "array", "items": {"type": "string"}},
            "location": {"type": "string"},
            "remote_type": {
                "type": ["string", "null"],
                "enum": ["remote", "hybrid", "onsite", None],
            },
            "employment_type": {
                "type": ["string", "null"],
                "enum": ["full_time", "part_time", "contract", "internship", None],
            },
            "seniority": {"type": ["string", "null"]},
            "salary_min": {"type": ["number", "null"]},
            "salary_max": {"type": ["number", "null"]},
            "salary_currency": {"type": ["string", "null"]},
            "application_url": {"type": "string"},
            "posted_at": {"type": ["string", "null"]},
        },
        "required": [
            "external_job_id",
            "company_name",
            "title",
            "description",
            "application_url",
        ],
    }
