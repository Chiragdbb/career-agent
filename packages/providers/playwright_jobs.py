"""Playwright job scraper — primary free tier for known board structures.

Per-source selector configs extract only the StructuredJobPosting fields.
Never targets LinkedIn or other anti-bot-protected sites.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlparse

from packages.domain.job_posting import StructuredJobPosting
from packages.providers.base import ProviderMetadata, UsageInfo
from packages.providers.exceptions import (
    ProviderError,
    ProviderNotConfiguredError,
    ProviderValidationError,
)


@dataclass(frozen=True)
class JobSourceSelectors:
    """CSS selectors / extractors for one known job board."""

    name: str
    host_patterns: tuple[str, ...]
    title: str
    description: str
    location: str | None = None
    company_name: str | None = None
    requirements: str | None = None
    external_id_from_url: Callable[[str], str | None] | None = None
    company_from_url: Callable[[str], str | None] | None = None


_GH_JOB_RE = re.compile(
    r"https?://(?:job-)?boards\.greenhouse\.io/([^/]+)/jobs/(\d+)",
    re.IGNORECASE,
)


def _greenhouse_external_id(url: str) -> str | None:
    match = _GH_JOB_RE.search(url)
    return match.group(2) if match else None


def _greenhouse_company_slug(url: str) -> str | None:
    match = _GH_JOB_RE.search(url)
    return match.group(1) if match else None


GREENHOUSE_SELECTORS = JobSourceSelectors(
    name="greenhouse",
    host_patterns=(
        "boards.greenhouse.io",
        "job-boards.greenhouse.io",
    ),
    title="h1.app-title, h1.section-header, .job__title, h1",
    description="#content, .job__description, #job_description, .content",
    location=".location, .job__location, .app-location",
    company_name=None,
    requirements=None,
    external_id_from_url=_greenhouse_external_id,
    company_from_url=_greenhouse_company_slug,
)

KNOWN_JOB_SOURCES: tuple[JobSourceSelectors, ...] = (GREENHOUSE_SELECTORS,)

# Domains we refuse to scrape with Playwright (anti-bot / ToS).
BLOCKED_HOST_SUFFIXES = (
    "linkedin.com",
    "www.linkedin.com",
    "indeed.com",
    "glassdoor.com",
)


def match_job_source(url: str) -> JobSourceSelectors | None:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    if any(host == blocked or host.endswith("." + blocked) for blocked in BLOCKED_HOST_SUFFIXES):
        return None
    for source in KNOWN_JOB_SOURCES:
        for pattern in source.host_patterns:
            if host == pattern or host.endswith("." + pattern):
                return source
    return None


def is_known_job_board(url: str) -> bool:
    return match_job_source(url) is not None


def parse_greenhouse_dom(fields: dict[str, str | None], *, url: str) -> StructuredJobPosting:
    """Build StructuredJobPosting from already-extracted field text (testable without browser)."""
    external_id = _greenhouse_external_id(url)
    if not external_id:
        raise ProviderValidationError(
            "Greenhouse URL missing job id",
            provider="playwright-jobs",
            operation="parse",
        )
    slug = _greenhouse_company_slug(url) or "unknown"
    title = (fields.get("title") or "").strip()
    description = (fields.get("description") or "").strip()
    if not title or not description:
        raise ProviderValidationError(
            "Greenhouse page missing title or description",
            provider="playwright-jobs",
            operation="parse",
        )
    location = (fields.get("location") or "").strip()
    company_name = (fields.get("company_name") or "").strip() or slug.replace("-", " ").title()
    requirements = _split_requirements(description)
    skills = _heuristic_skills(description)
    remote = _infer_remote(location + " " + description)
    return StructuredJobPosting(
        external_job_id=external_id,
        source="playwright",
        company_name=company_name,
        company_domain=None,
        title=title,
        description=_clean_prose(description),
        requirements=requirements,
        skills=skills,
        location=location,
        remote_type=remote,
        employment_type=None,
        seniority=None,
        salary_min=None,
        salary_max=None,
        salary_currency=None,
        application_url=url.split("?")[0].rstrip("/"),
        posted_at=None,
        scraped_at=datetime.now(timezone.utc),
    )


def _clean_prose(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    # Cap length so LLM context stays bounded if this ever re-enters an LLM path.
    return cleaned[:12_000]


def _split_requirements(description: str) -> list[str]:
    lines = []
    for line in description.splitlines():
        stripped = line.strip(" •-\t")
        if stripped and (
            stripped.lower().startswith("require")
            or line.strip().startswith(("-", "*", "•"))
        ):
            if len(stripped) > 8:
                lines.append(stripped[:300])
        if len(lines) >= 20:
            break
    return lines


def _heuristic_skills(description: str) -> list[str]:
    known = (
        "Python",
        "TypeScript",
        "JavaScript",
        "React",
        "Node.js",
        "SQL",
        "PostgreSQL",
        "AWS",
        "Docker",
        "Kubernetes",
        "Go",
        "Java",
        "Rust",
        "LLM",
        "Machine Learning",
    )
    found: list[str] = []
    lower = description.lower()
    for skill in known:
        if skill.lower() in lower:
            found.append(skill)
    return found


def _infer_remote(text: str) -> str | None:
    lower = text.lower()
    if "hybrid" in lower:
        return "hybrid"
    if "remote" in lower or "work from home" in lower:
        return "remote"
    if "on-site" in lower or "onsite" in lower or "in office" in lower:
        return "onsite"
    return None


@dataclass
class PlaywrightJobsScrapeResult:
    posting: StructuredJobPosting
    usage: UsageInfo


class PlaywrightJobsProvider:
    """Scrape known job boards via Playwright into StructuredJobPosting."""

    def __init__(self, *, headless: bool = True, default_timeout_ms: int = 30_000) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise ProviderNotConfiguredError(
                "playwright is not installed; use MockPlaywrightJobsProvider in CI",
                provider="playwright-jobs",
            ) from exc
        self._sync_playwright = sync_playwright
        self._headless = headless
        self._default_timeout_ms = default_timeout_ms
        self._meta = ProviderMetadata(
            name="playwright-jobs",
            vendor="playwright",
            capabilities=frozenset({"job_scrape", "structured_extract"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def can_handle(self, url: str) -> bool:
        return is_known_job_board(url)

    def scrape_job(self, url: str, *, timeout_seconds: float = 30.0) -> PlaywrightJobsScrapeResult:
        started = time.perf_counter()
        source = match_job_source(url)
        if source is None:
            raise ProviderValidationError(
                f"No Playwright selector config for URL host: {url}",
                provider=self._meta.name,
                operation="scrape_job",
            )
        host = (urlparse(url).hostname or "").lower()
        if any(host.endswith(blocked) for blocked in BLOCKED_HOST_SUFFIXES):
            raise ProviderValidationError(
                f"Playwright jobs scraper refuses blocked host: {host}",
                provider=self._meta.name,
                operation="scrape_job",
            )

        fields = self._extract_fields(url, source, timeout_seconds=timeout_seconds)
        if source.name == "greenhouse":
            posting = parse_greenhouse_dom(fields, url=url)
        else:
            raise ProviderError(
                f"Unhandled job source config: {source.name}",
                provider=self._meta.name,
                operation="scrape_job",
            )
        latency = (time.perf_counter() - started) * 1000.0
        return PlaywrightJobsScrapeResult(
            posting=posting,
            usage=UsageInfo(
                operation="job_extraction",
                unit_type="requests",
                units=1.0,
                latency_ms=latency,
                provider=self._meta.name,
                estimated_cost_usd=0.0,
                extra={"source_config": source.name, "url": url},
            ),
        )

    def _extract_fields(
        self,
        url: str,
        source: JobSourceSelectors,
        *,
        timeout_seconds: float,
    ) -> dict[str, str | None]:
        pw = self._sync_playwright().start()
        try:
            browser = pw.chromium.launch(headless=self._headless)
            try:
                page = browser.new_page()
                page.set_default_timeout(int(timeout_seconds * 1000) or self._default_timeout_ms)
                page.goto(url, wait_until="domcontentloaded")
                return {
                    "title": _first_text(page, source.title),
                    "description": _first_text(page, source.description),
                    "location": _first_text(page, source.location) if source.location else None,
                    "company_name": (
                        _first_text(page, source.company_name) if source.company_name else None
                    ),
                }
            finally:
                browser.close()
        finally:
            pw.stop()


def _first_text(page: Any, selector_list: str) -> str | None:
    for selector in selector_list.split(","):
        sel = selector.strip()
        if not sel:
            continue
        try:
            loc = page.locator(sel).first
            if loc.count() == 0:
                continue
            text = (loc.inner_text() or "").strip()
            if text:
                return text
        except Exception:
            continue
    return None


@dataclass
class MockPlaywrightJobsProvider:
    """Deterministic stand-in for CI."""

    postings_by_url: dict[str, StructuredJobPosting] = field(default_factory=dict)
    fail_with: Exception | None = None

    def __post_init__(self) -> None:
        self._meta = ProviderMetadata(
            name="mock-playwright-jobs",
            vendor="mock",
            capabilities=frozenset({"job_scrape", "structured_extract"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def can_handle(self, url: str) -> bool:
        return url in self.postings_by_url or is_known_job_board(url)

    def scrape_job(self, url: str, *, timeout_seconds: float = 30.0) -> PlaywrightJobsScrapeResult:
        if self.fail_with is not None:
            raise self.fail_with
        if url in self.postings_by_url:
            posting = self.postings_by_url[url]
        elif is_known_job_board(url):
            posting = parse_greenhouse_dom(
                {
                    "title": "Software Engineer",
                    "description": "Build APIs with Python and SQL. Requirements: 3+ years.",
                    "location": "Remote",
                    "company_name": "Acme",
                },
                url=url,
            )
        else:
            raise ProviderValidationError(
                "Mock has no posting for URL",
                provider=self._meta.name,
                operation="scrape_job",
            )
        return PlaywrightJobsScrapeResult(
            posting=posting,
            usage=UsageInfo(
                operation="job_extraction",
                unit_type="requests",
                units=1.0,
                latency_ms=1.0,
                provider=self._meta.name,
                estimated_cost_usd=0.0,
            ),
        )
