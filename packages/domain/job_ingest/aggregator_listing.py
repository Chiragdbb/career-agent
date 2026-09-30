"""Aggregator listing pages — card-level extract, dedupe, and access checks."""

from __future__ import annotations

import hashlib
import re
from urllib.parse import urljoin, urlparse

from pydantic import BaseModel, Field, field_validator

from packages.domain.job_ingest.aggregator_registry import (
    extract_aggregator_job_id,
    is_aggregator_host,
    is_aggregator_job_detail_url,
    is_linkedin_job_detail_url,
    is_naukri_job_detail_url,
    is_scrape_policy_blocked_url,
)

_PAGE_NUM_RE = re.compile(r"(?:^|[?&/])page[=_-]?(\d+)", re.IGNORECASE)

_LOGIN_GATE_MARKERS = (
    "sign in to view",
    "sign in to see",
    "login to view",
    "join linkedin",
    "authwall",
    "captcha",
    "verify you are human",
    "please log in",
)

_HTTP_BLOCKED_MARKERS = (
    "403 forbidden",
    "access denied",
    "request blocked",
)


class AggregatorListingCard(BaseModel):
    """One job row visible on a listing/search page (not a full JD fetch)."""

    title: str = Field(min_length=1)
    company_name: str | None = None
    location: str | None = None
    snippet: str | None = None
    posted_at: str | None = None
    aggregator_job_id: str | None = None
    card_url: str | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise ValueError("title required")
        return cleaned


def aggregator_card_dedupe_id(
    *,
    aggregator_job_id: str | None,
    company_name: str | None,
    title: str,
    location: str | None,
) -> str:
    if aggregator_job_id and aggregator_job_id.strip():
        return aggregator_job_id.strip()
    basis = "|".join(
        [
            (company_name or "").strip().lower(),
            title.strip().lower(),
            (location or "").strip().lower(),
        ]
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32]


def company_domain_slug(company_name: str | None) -> str | None:
    if not company_name or not company_name.strip():
        return None
    slug = re.sub(r"[^a-z0-9]+", "-", company_name.strip().lower()).strip("-")
    return slug or None


def listing_page_access(
    url: str,
    *,
    markdown: str = "",
    html: str | None = None,
    http_status: int | None = None,
) -> tuple[bool, str | None]:
    """Return (accessible, reason) — detect pagination gates and login walls."""
    parsed = urlparse(url)
    blob = f"{parsed.query} {parsed.path}"
    page_match = _PAGE_NUM_RE.search(blob)
    if page_match and int(page_match.group(1)) > 1:
        return False, "listing_pagination_gated"

    if http_status in (401, 403, 429):
        return False, f"http_{http_status}"

    text = f"{markdown}\n{html or ''}".lower()[:8000]
    if any(marker in text for marker in _LOGIN_GATE_MARKERS):
        return False, "listing_login_gated"
    if http_status == 403 or any(marker in text for marker in _HTTP_BLOCKED_MARKERS):
        return False, "http_blocked"
    return True, None


def card_to_job_url(card: AggregatorListingCard, *, listing_page: str) -> str:
    """Prefer card URL from the listing; resolve relative links against the listing page."""
    raw = (card.card_url or "").strip()
    if raw:
        if raw.startswith("http"):
            return raw
        return urljoin(listing_page, raw)
    job_id = card.aggregator_job_id or extract_aggregator_job_id(card.card_url)
    if job_id and ":" in job_id:
        _slug, _val = job_id.split(":", 1)
        if _slug == "linkedin" and _val.isdigit():
            return f"https://www.linkedin.com/jobs/view/{_val}"
    return listing_page


def should_accept_card_job_url(job_url: str) -> bool:
    """Card rows must not expand into another listing page (except known detail URLs)."""
    if is_scrape_policy_blocked_url(job_url):
        return True
    if is_aggregator_job_detail_url(job_url):
        return True
    if is_aggregator_host(job_url) and not is_naukri_job_detail_url(job_url):
        from packages.domain.job_urls import is_likely_listing_page

        if is_likely_listing_page(job_url) and not is_linkedin_job_detail_url(job_url):
            return False
    return True
