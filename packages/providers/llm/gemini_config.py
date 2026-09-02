"""Gemini tier and rate-limit configuration."""

from __future__ import annotations

import os

GEMINI_EXTRACTION_MODEL = "gemini-2.5-flash-lite"
GEMINI_DEFAULT_MODEL = "gemini-2.5-flash"

_DEFAULT_RPM_BY_TIER: dict[str, int] = {
    "free": 10,
    "paid": 1000,
}


def normalize_gemini_tier(value: str | None) -> str:
    tier = (value or "free").strip().lower()
    return tier if tier in _DEFAULT_RPM_BY_TIER else "free"


def gemini_rpm_for_tier(tier: str | None) -> int:
    """Requests-per-minute ceiling for the configured Gemini tier."""
    normalized = normalize_gemini_tier(tier)
    env_key = f"GEMINI_RPM_{normalized.upper()}"
    raw = (os.getenv(env_key) or "").strip()
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    return _DEFAULT_RPM_BY_TIER[normalized]
