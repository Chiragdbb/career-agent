"""URL helpers for job discovery."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from packages.domain.job_ingest.aggregator_registry import (
    AGGREGATOR_HOST_SUFFIXES,
    is_aggregator_host,
    is_aggregator_job_detail_url,
    is_employer_ats_board_listing,
    is_employer_ats_single_job,
    is_naukri_job_detail_url,
)

_GH_JOB_RE = re.compile(    r"/jobs/\d+(?:/|$|\?)",
    re.IGNORECASE,
)
_ASHBY_JOB_RE = re.compile(
    r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?:/|$|\?)",
    re.IGNORECASE,
)
_LEVER_JOB_RE = re.compile(
    r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)

# Path fragments that usually indicate search/listing pages, not a single job posting.
_LISTING_PATH_MARKERS = (
    "/search/",
    "/categories/",
    "/category/",
    "/jobs/q",
    "/jobs/q-",
    "/q-",
    "/browse/",
    "/collections/",
)

_LISTING_QUERY_MARKERS = (
    "q=",
    "query=",
    "keywords=",
    "search=",
)


def is_aggregator_listing_page(url: str) -> bool:
    """Search/listing on any third-party job aggregator (card ingest path)."""
    if not is_likely_listing_page(url):
        return False
    if is_employer_ats_board_listing(url) or is_employer_ats_single_job(url):
        return False
    if is_aggregator_job_detail_url(url):
        return False
    return is_aggregator_host(url)


def is_likely_listing_page(url: str) -> bool:
    """Return True when a URL is probably a job board listing, not one posting."""
    raw = (url or "").strip()
    if not raw:
        return True

    parsed = urlparse(raw)
    path = (parsed.path or "").lower()
    query = (parsed.query or "").lower()

    if any(marker in path for marker in _LISTING_PATH_MARKERS):
        return True

    # Indeed-style search pages: /q-role-location-jobs.html
    if "indeed.com" in (parsed.netloc or "").lower() and "/q-" in path:
        return True

    # Dice-style search: /jobs/q-remote+developer-jobs
    if "dice.com" in (parsed.netloc or "").lower() and "/jobs/q" in path:
        return True

    # Generic search query params on job paths
    if "/jobs" in path and any(marker in query for marker in _LISTING_QUERY_MARKERS):
        return True

    host = (parsed.netloc or "").lower()

    # LinkedIn aggregated search/listing URLs (not /jobs/view/…)
    if "linkedin.com" in host and "/jobs/" in path:
        if "/jobs/view/" in path or "/jobs/viewjob" in path:
            return False
        if re.search(r"/jobs/[^/]+-jobs-", path, re.IGNORECASE):
            return True
        if path.rstrip("/").endswith("/jobs") or "/jobs/search" in path:
            return True

    # Greenhouse board home without a numeric job id
    if "greenhouse.io" in host and not _GH_JOB_RE.search(path):
        return True

    # Ashby company page without a job UUID
    if "ashbyhq.com" in host and not _ASHBY_JOB_RE.search(path):
        return True

    # Lever board root (job posts include a UUID segment)
    if "jobs.lever.co" in host and not _LEVER_JOB_RE.search(path):
        return True

    # Naukri city/search listing pages (detail postings use job-listings-…-{id})
    if "naukri.com" in host:
        if is_naukri_job_detail_url(url):
            return False
        if "-jobs-in-" in path or path.rstrip("/").endswith("/job-listings"):
            return True

    # Generic aggregator search (host heuristic applied in is_aggregator_listing_page)
    if is_aggregator_host(url) and is_aggregator_job_detail_url(url):
        return False
    if is_aggregator_host(url) and (
        any(marker in path for marker in _LISTING_PATH_MARKERS)
        or ("/jobs" in path and any(marker in query for marker in _LISTING_QUERY_MARKERS))
    ):
        return True

    # ZipRecruiter / Indeed-style search paths
    if "ziprecruiter.com" in host and ("/jobs-search" in path or "/candidate/search" in path):
        return True

    return False


_INVALID_JOB_TITLE_MARKERS = (
    "page not found",
    "404",
    "closed job",
    "job no longer",
    "position filled",
    "job search",
    "kiosk mode",
)


def is_invalid_job_title(title: str | None) -> bool:
    """True when extracted title clearly indicates a non-posting page."""
    text = (title or "").strip().lower()
    if not text or len(text) < 2:
        return True
    return any(marker in text for marker in _INVALID_JOB_TITLE_MARKERS)
