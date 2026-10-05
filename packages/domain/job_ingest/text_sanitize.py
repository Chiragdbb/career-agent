"""Plain-text cleanup for scraped job descriptions."""

from __future__ import annotations

import html
import re


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\f\v]+")
_LITERAL_NL_RE = re.compile(r"(?:\\r\\n|\\n|\\r)")


def strip_html_to_text(value: str | None) -> str:
    """Remove HTML tags and normalize whitespace for display and matching.

    Unescape before stripping so encoded tags (``&lt;p&gt;``) do not survive
    as visible markup after a single unescape pass.
    """
    if not value:
        return ""
    text = str(value)
    # Encoded tags first, then strip, then unescape entities in content.
    text = html.unescape(text)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = _LITERAL_NL_RE.sub("\n", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WS_RE.sub(" ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
