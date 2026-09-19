"""Playwright contact scrape — company-owned public pages only.

Never scrapes LinkedIn or other anti-bot-protected profile databases.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from packages.providers.base import ProviderMetadata, UsageInfo
from packages.providers.exceptions import (
    ProviderNotConfiguredError,
    ProviderValidationError,
)
from packages.providers.playwright_jobs import BLOCKED_HOST_SUFFIXES

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_NAME_TITLE_RE = re.compile(
    r"(?P<name>[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s*[-–,|]\s*(?P<title>[^\n]{3,80})",
)

TEAM_PATH_HINTS = (
    "/about",
    "/team",
    "/people",
    "/leadership",
    "/company",
    "/our-team",
    "/staff",
)


@dataclass(frozen=True)
class ScrapedContactHit:
    full_name: str
    title: str | None = None
    email: str | None = None
    email_confidence: str = "unverified"  # verified | guessed | unverified
    source_url: str | None = None


@dataclass
class PlaywrightContactsResult:
    contacts: list[ScrapedContactHit]
    usage: UsageInfo


def assert_company_owned_url(url: str, company_domain: str | None) -> None:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    if any(host == b or host.endswith("." + b) for b in BLOCKED_HOST_SUFFIXES):
        raise ProviderValidationError(
            f"Playwright contacts refuses anti-bot host: {host}",
            provider="playwright-contacts",
            operation="contact_lookup",
        )
    if company_domain:
        domain = company_domain.lower().removeprefix("www.")
        if host != domain and not host.endswith("." + domain):
            raise ProviderValidationError(
                f"URL host {host} is not company domain {domain}",
                provider="playwright-contacts",
                operation="contact_lookup",
            )


def parse_team_page_text(text: str, *, source_url: str, company_domain: str | None) -> list[ScrapedContactHit]:
    """Extract contacts from plain page text (testable without browser)."""
    hits: list[ScrapedContactHit] = []
    emails = {e.lower() for e in _EMAIL_RE.findall(text)}
    # Prefer emails on the company domain when known.
    company_emails = sorted(
        e for e in emails if company_domain and e.endswith("@" + company_domain.lower())
    )
    pattern_example = company_emails[0] if company_emails else None

    for match in _NAME_TITLE_RE.finditer(text):
        name = match.group("name").strip()
        title = match.group("title").strip()
        if len(name.split()) < 2:
            continue
        email = None
        confidence = "unverified"
        if pattern_example:
            # Infer first.last@domain from a verified example pattern on the page.
            local = pattern_example.split("@", 1)[0]
            if "." in local:
                parts = name.lower().split()
                if len(parts) >= 2:
                    guessed = f"{parts[0]}.{parts[-1]}@{company_domain}"
                    # Never invent as verified — mark guessed only.
                    email = guessed
                    confidence = "guessed"
        hits.append(
            ScrapedContactHit(
                full_name=name,
                title=title[:120],
                email=email,
                email_confidence=confidence,
                source_url=source_url,
            )
        )
        if len(hits) >= 10:
            break

    # Also surface any on-page emails with unknown names as last resort.
    if not hits and company_emails:
        for email in company_emails[:3]:
            local = email.split("@", 1)[0]
            name = local.replace(".", " ").replace("_", " ").title()
            hits.append(
                ScrapedContactHit(
                    full_name=name,
                    title=None,
                    email=email,
                    email_confidence="verified",
                    source_url=source_url,
                )
            )
    return hits


class PlaywrightContactsProvider:
    """Scrape company team/about pages for public contact signals."""

    def __init__(self, *, headless: bool = True, default_timeout_ms: int = 30_000) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise ProviderNotConfiguredError(
                "playwright is not installed; use MockPlaywrightContactsProvider in CI",
                provider="playwright-contacts",
            ) from exc
        self._sync_playwright = sync_playwright
        self._headless = headless
        self._default_timeout_ms = default_timeout_ms
        self._meta = ProviderMetadata(
            name="playwright-contacts",
            vendor="playwright",
            capabilities=frozenset({"contact_lookup"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def find_contacts(
        self,
        *,
        company_domain: str,
        page_urls: list[str] | None = None,
        timeout_seconds: float = 30.0,
    ) -> PlaywrightContactsResult:
        started = time.perf_counter()
        domain = company_domain.lower().removeprefix("www.")
        urls = page_urls or [f"https://{domain}{path}" for path in TEAM_PATH_HINTS[:4]]
        all_hits: list[ScrapedContactHit] = []
        seen: set[str] = set()

        pw = self._sync_playwright().start()
        try:
            browser = pw.chromium.launch(headless=self._headless)
            try:
                page = browser.new_page()
                page.set_default_timeout(int(timeout_seconds * 1000) or self._default_timeout_ms)
                for url in urls:
                    try:
                        assert_company_owned_url(url, domain)
                        page.goto(url, wait_until="domcontentloaded")
                        text = page.inner_text("body")
                        for hit in parse_team_page_text(text, source_url=url, company_domain=domain):
                            key = hit.full_name.lower()
                            if key in seen:
                                continue
                            seen.add(key)
                            all_hits.append(hit)
                        if all_hits:
                            break
                    except Exception:
                        continue
            finally:
                browser.close()
        finally:
            pw.stop()

        return PlaywrightContactsResult(
            contacts=all_hits,
            usage=UsageInfo(
                operation="contact_lookup",
                unit_type="requests",
                units=1.0,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                provider=self._meta.name,
                estimated_cost_usd=0.0,
                extra={"domain": domain, "found": len(all_hits)},
            ),
        )


@dataclass
class MockPlaywrightContactsProvider:
    contacts: list[ScrapedContactHit] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._meta = ProviderMetadata(
            name="mock-playwright-contacts",
            vendor="mock",
            capabilities=frozenset({"contact_lookup"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def find_contacts(
        self,
        *,
        company_domain: str,
        page_urls: list[str] | None = None,
        timeout_seconds: float = 30.0,
    ) -> PlaywrightContactsResult:
        return PlaywrightContactsResult(
            contacts=list(self.contacts),
            usage=UsageInfo(
                operation="contact_lookup",
                unit_type="requests",
                units=1.0,
                latency_ms=1.0,
                provider=self._meta.name,
                estimated_cost_usd=0.0,
                extra={"domain": company_domain, "found": len(self.contacts)},
            ),
        )
