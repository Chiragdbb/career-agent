from packages.domain.job_ingest.text_sanitize import strip_html_to_text


def test_strip_html_to_text() -> None:
    raw = "<p>Hello <strong>world</strong></p><ul><li>One</li></ul>"
    assert strip_html_to_text(raw) == "Hello world One"
    assert strip_html_to_text("&amp; remote") == "& remote"
