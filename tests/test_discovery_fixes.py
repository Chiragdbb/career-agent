"""Tests for discovery scraping and model fixes."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from packages.domain.discovery_logger import DiscoveryFileLogger, discovery_log_enabled
from packages.domain.job_urls import is_likely_listing_page
from packages.providers.groq_models import DEFAULT_GROQ_MODEL, normalize_groq_model
from packages.providers.scraper import MockScraperProvider, ScrapeRequest, ScrapedPage
from packages.providers.scraper_fallback import FallbackScraperProvider
from packages.providers.exceptions import ProviderError


def test_normalize_groq_model_migrates_deprecated() -> None:
    assert normalize_groq_model("llama-3.3-70b-versatile") == DEFAULT_GROQ_MODEL
    assert normalize_groq_model("openai/gpt-oss-120b") == "openai/gpt-oss-120b"


@pytest.mark.parametrize(
    "url",
    [
        "https://builtin.com/jobs/as/india/bangalore/dev-engineering/search/web-developer",
        "https://weworkremotely.com/categories/remote-full-stack-programming-jobs",
        "https://www.indeed.com/q-full-stack-developer-remote-jobs.html",
        "https://www.dice.com/jobs/q-remote+full+stack+developer-jobs",
    ],
)
def test_is_likely_listing_page_detects_search_urls(url: str) -> None:
    assert is_likely_listing_page(url) is True


def test_is_likely_listing_page_allows_job_posting() -> None:
    assert (
        is_likely_listing_page(
            "https://boards.greenhouse.io/acme/jobs/12345"
        )
        is False
    )


def test_fallback_scraper_tries_next_provider() -> None:
  class FailingScraper(MockScraperProvider):
      def scrape_url(self, request: ScrapeRequest) -> ScrapedPage:
          raise ProviderError("down", provider="fail", operation="scrape_url")

  working = MockScraperProvider(
      pages=[ScrapedPage(url="https://example.com/job", title="Job", markdown="# Job")]
  )
  scraper = FallbackScraperProvider([FailingScraper(), working])
  page = scraper.scrape_url(ScrapeRequest(url="https://example.com/job"))
  assert page.markdown == "# Job"


def test_discovery_file_logger_writes_jsonl(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    log_file = tmp_path / "discovery.log"
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DISCOVERY_LOG_FILE", str(log_file))

    assert discovery_log_enabled() is True

    run_id = uuid.uuid4()
    logger = DiscoveryFileLogger(run_id)
    logger.log("test_event", url="https://example.com", status="ok")

    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["event"] == "test_event"
    assert record["run_id"] == str(run_id)
    assert record["url"] == "https://example.com"
