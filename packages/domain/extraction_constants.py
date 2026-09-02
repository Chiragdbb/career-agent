"""Configurable limits for job extraction from scraped content."""

from __future__ import annotations

# Groq / OpenAI — conservative limits (~6k tokens).
EXTRACTION_CONTENT_MAX_CHARS = 24_000
EXTRACTION_CONTENT_RETRY_MAX_CHARS = EXTRACTION_CONTENT_MAX_CHARS // 2
EXTRACTION_CONTENT_PREFILTER_MAX_CHARS = 40_000

# Gemini 2.5 Flash — 1M token context; only truncate near context window.
# ~900k chars leaves room for system prompt, schema, and model output.
GEMINI_EXTRACTION_CONTENT_MAX_CHARS = 900_000
GEMINI_EXTRACTION_CONTENT_RETRY_MAX_CHARS = GEMINI_EXTRACTION_CONTENT_MAX_CHARS // 2
GEMINI_EXTRACTION_CONTENT_PREFILTER_MAX_CHARS = GEMINI_EXTRACTION_CONTENT_MAX_CHARS

_GEMINI_PROVIDER_NAME = "gemini-llm"


def extraction_max_chars_for_provider(provider_name: str) -> int:
    if provider_name == _GEMINI_PROVIDER_NAME:
        return GEMINI_EXTRACTION_CONTENT_MAX_CHARS
    return EXTRACTION_CONTENT_MAX_CHARS


def extraction_retry_max_chars_for_provider(provider_name: str) -> int:
    if provider_name == _GEMINI_PROVIDER_NAME:
        return GEMINI_EXTRACTION_CONTENT_RETRY_MAX_CHARS
    return EXTRACTION_CONTENT_RETRY_MAX_CHARS


def extraction_prefilter_max_chars_for_provider(provider_name: str) -> int:
    if provider_name == _GEMINI_PROVIDER_NAME:
        return GEMINI_EXTRACTION_CONTENT_PREFILTER_MAX_CHARS
    return EXTRACTION_CONTENT_PREFILTER_MAX_CHARS
