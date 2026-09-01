"""Configurable limits for job extraction from scraped content."""

from __future__ import annotations

# ~6,000 tokens — job descriptions front-load requirements.
EXTRACTION_CONTENT_MAX_CHARS = 24_000

# Half-size retry after json_validate_failed or token-limit errors.
EXTRACTION_CONTENT_RETRY_MAX_CHARS = EXTRACTION_CONTENT_MAX_CHARS // 2

# Pages larger than this are probably listings/aggregators, not one posting.
EXTRACTION_CONTENT_PREFILTER_MAX_CHARS = 40_000
