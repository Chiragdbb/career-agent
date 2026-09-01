"""Truncate untrusted scraped content before LLM extraction."""

from __future__ import annotations

_TRUNCATION_NOTICE = "\n\n[... content truncated for extraction ...]"


def truncate_for_extraction(content: str, max_chars: int) -> str:
    """Keep the first *max_chars* characters (job details usually appear first)."""
    text = content or ""
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    if max_chars <= len(_TRUNCATION_NOTICE):
        return text[:max_chars]
    keep = max_chars - len(_TRUNCATION_NOTICE)
    return text[:keep] + _TRUNCATION_NOTICE
