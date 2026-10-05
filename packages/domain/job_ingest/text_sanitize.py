"""Plain-text cleanup for scraped job descriptions."""

from __future__ import annotations

import html
import re


def strip_html_to_text(value: str | None) -> str:
    """Remove HTML tags and normalize whitespace for display and matching."""
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", str(value))
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
