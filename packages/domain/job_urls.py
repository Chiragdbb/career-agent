"""URL helpers for job discovery."""

from __future__ import annotations

from urllib.parse import urlparse

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

    return False
