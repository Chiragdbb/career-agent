"""Scrapling scraper adapter (mocked / optional live)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from packages.providers.scraper import ScrapeRequest
from packages.providers.scrapling_scraper import (
    MockScraplingScraperProvider,
    ScraplingScraperProvider,
    _job_board_markdown,
)


def test_mock_scrapling_scraper_returns_markdown() -> None:
    provider = MockScraplingScraperProvider(markdown="# Engineer\n\nBuild things.")
    page = provider.scrape_url(ScrapeRequest(url="https://example.com/jobs/1"))
    assert "Engineer" in page.markdown
    assert page.metadata.get("fetcher") == "mock"


def test_job_board_markdown_from_selectors() -> None:
    response = MagicMock()
    response.css.side_effect = lambda sel: {
        "h1": [MagicMock(get_all_text=lambda: "Backend Engineer")],
        "#content": [MagicMock(get_all_text=lambda: "Python and SQL required.")],
        ".location": [MagicMock(get_all_text=lambda: "Remote")],
    }.get(sel.split(",")[0].strip(), [])

    url = "https://boards.greenhouse.io/acme/jobs/12345"
    md = _job_board_markdown(url, response)
    assert md is not None
    assert "Backend Engineer" in md
    assert "Python and SQL" in md
    assert "Remote" in md


def test_scrapling_provider_http_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_response = MagicMock()
    fake_response.status = 200
    fake_response.css.side_effect = lambda sel: {
        "title": [MagicMock(get_all_text=lambda: "Example")],
        "h1": [MagicMock(get_all_text=lambda: "Example Domain")],
    }.get(sel.split(",")[0].strip(), [])
    fake_response.get_all_text.return_value = "Example Domain\nBody text"
    fake_response.html_content = "<html></html>"
    fake_response.markdown.side_effect = ModuleNotFoundError("markdownify")

    fake_fetcher = MagicMock()
    fake_fetcher.get.return_value = fake_response
    fake_fetcher.configure = MagicMock()

    with patch.dict(
        "sys.modules",
        {
            "scrapling": MagicMock(),
            "scrapling.fetchers": MagicMock(Fetcher=fake_fetcher),
        },
    ):
        provider = ScraplingScraperProvider(fetcher="http")
        page = provider.scrape_url(ScrapeRequest(url="https://example.com"))

    assert "Example" in page.markdown
    assert page.metadata["fetcher"] == "http"
    fake_fetcher.get.assert_called_once()
