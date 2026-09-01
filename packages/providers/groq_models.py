"""Groq model IDs and migration for deprecated models."""

from __future__ import annotations

# Groq retired llama-3.3-70b-versatile on 2026-08-16 (developer tier).
# https://console.groq.com/docs/deprecations
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"

_DEPRECATED_GROQ_MODELS: dict[str, str] = {
    "llama-3.3-70b-versatile": DEFAULT_GROQ_MODEL,
    "llama-3.1-8b-instant": "openai/gpt-oss-20b",
}


def normalize_groq_model(model: str) -> str:
    """Map retired Groq model IDs to their replacements."""
    cleaned = (model or "").strip()
    if not cleaned:
        return DEFAULT_GROQ_MODEL
    return _DEPRECATED_GROQ_MODELS.get(cleaned, cleaned)
