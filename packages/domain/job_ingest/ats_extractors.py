"""Deterministic ATS job extractors (preferred over generic scrape)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from packages.domain.job_posting import StructuredJobPosting
from packages.providers.http_utils import request_with_retries

_GH_BOARD_RE = re.compile(
    r"https?://(?:job-)?boards\.greenhouse\.io/([^/]+)/jobs/(\d+)",
    re.IGNORECASE,
)
_LEVER_RE = re.compile(
    r"https?://jobs\.lever\.co/([^/]+)/([0-9a-f-]{36})(?:/apply)?/?",
    re.IGNORECASE,
)
_ASHBY_RE = re.compile(
    r"https?://jobs\.ashbyhq\.com/([^/]+)/([0-9a-f-]{36})",
    re.IGNORECASE,
)


def extract_from_ats_url(url: str) -> StructuredJobPosting | None:
    """Return structured posting when URL matches a supported ATS pattern."""
    if match := _GH_BOARD_RE.search(url):
        return _greenhouse_api(match.group(1), match.group(2), url=url)
    if _LEVER_RE.search(url) or _ASHBY_RE.search(url):
        return None  # Lever/Ashby DOM extractors — future work
    return None


def _greenhouse_api(board: str, job_id: str, *, url: str) -> StructuredJobPosting | None:
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}"
    try:
        response = request_with_retries(
            method="GET",
            url=api_url,
            provider="greenhouse-ats-api",
            operation="job_extraction",
            timeout_seconds=25.0,
            max_retries=2,
        )
        data = response.json()
    except Exception:
        return None
    if not isinstance(data, dict):
        return None

    title = str(data.get("title") or "").strip()
    content = str(data.get("content") or "").strip()
    if not title or not content:
        return None

    from packages.domain.job_urls import is_invalid_job_title

    if is_invalid_job_title(title):
        return None

    location_name = ""
    locs = data.get("location") or {}
    if isinstance(locs, dict):
        location_name = str(locs.get("name") or "").strip()

    departments = data.get("departments") or []
    seniority = None
    if isinstance(departments, list) and departments:
        seniority = str((departments[0] or {}).get("name") or "") or None

    company_name = board.replace("-", " ").title()
    metadata = data.get("metadata") or []
    skills: list[str] = []
    if isinstance(metadata, list):
        for item in metadata:
            if isinstance(item, dict) and item.get("name") == "Skills":
                val = item.get("value")
                if isinstance(val, str):
                    skills.extend(s.strip() for s in val.split(",") if s.strip())

    updated = data.get("updated_at") or data.get("first_published")
    posted = None
    if isinstance(updated, str) and len(updated) >= 10:
        try:
            from datetime import date

            posted = date.fromisoformat(updated[:10])
        except ValueError:
            posted = None

    domain = _company_domain_from_board(board)

    return StructuredJobPosting(
        external_job_id=job_id,
        source="ats_extractor",
        company_name=company_name,
        company_domain=domain,
        title=title,
        description=_strip_html(content),
        requirements=[],
        skills=skills,
        location=location_name,
        remote_type=_infer_remote(location_name, content),
        employment_type=None,
        seniority=seniority,
        salary_min=None,
        salary_max=None,
        salary_currency=None,
        application_url=url,
        posted_at=posted,
        scraped_at=datetime.now(timezone.utc),
    )


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _infer_remote(location: str, body: str) -> str | None:
    blob = f"{location} {body}".lower()
    if "remote" in blob and "hybrid" in blob:
        return "hybrid"
    if "remote" in blob:
        return "remote"
    if location:
        return "onsite"
    return None


def _company_domain_from_board(board: str) -> str | None:
    # Board slug is not always the corporate domain — leave for domain resolution.
    slug = board.strip().lower()
    if not slug:
        return None
    return f"{slug}.com"
