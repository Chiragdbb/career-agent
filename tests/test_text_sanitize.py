from packages.domain.job_ingest.text_sanitize import strip_html_to_text


def test_strip_html_to_text() -> None:
    raw = "<p>Hello <strong>world</strong></p><ul><li>One</li></ul>"
    assert strip_html_to_text(raw) == "Hello world One"
    assert strip_html_to_text("&amp; remote") == "& remote"


def test_strip_html_encoded_tags() -> None:
    raw = "&lt;p&gt;Hello &lt;b&gt;world&lt;/b&gt;&lt;/p&gt;"
    assert strip_html_to_text(raw) == "Hello world"


def test_strip_html_literal_newlines() -> None:
    raw = "Line one\\nLine two"
    assert "Line one" in strip_html_to_text(raw)
    assert "Line two" in strip_html_to_text(raw)
    assert "\\n" not in strip_html_to_text(raw)
