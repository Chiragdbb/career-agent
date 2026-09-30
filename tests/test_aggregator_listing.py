"""Aggregator listing card extract helpers."""

from __future__ import annotations

from packages.domain.job_ingest.aggregator_listing import (
    aggregator_card_dedupe_id,
    listing_page_access,
    should_accept_card_job_url,
)
from packages.domain.job_ingest.aggregator_registry import (
    extract_aggregator_job_id,
    is_aggregator_host,
    is_aggregator_job_detail_url,
    is_linkedin_job_detail_url,
    is_naukri_job_detail_url,
    is_scrape_policy_blocked_url,
)
from packages.domain.job_urls import is_aggregator_listing_page
from packages.domain.job_ingest.completeness import JobCompletenessService, aggregator_listing_max_score
from database.models.schema import Job


def test_linkedin_detail_blocked_from_scrape() -> None:
    url = "https://www.linkedin.com/jobs/view/1234567890"
    assert is_linkedin_job_detail_url(url) is True
    assert is_scrape_policy_blocked_url(url) is True


def test_naukri_detail_not_listing_page() -> None:
    url = "https://www.naukri.com/job-listings-senior-developer-acme-123456789"
    assert is_naukri_job_detail_url(url) is True


def test_naukri_city_search_is_listing() -> None:
    from packages.domain.job_urls import is_likely_listing_page

    url = "https://www.naukri.com/full-stack-developer-jobs-in-bangalore"
    assert is_likely_listing_page(url) is True
    assert is_naukri_job_detail_url(url) is False


def test_extract_linkedin_job_id() -> None:
    assert extract_aggregator_job_id("https://www.linkedin.com/jobs/view/999") == "linkedin:999"


def test_dedupe_prefers_embedded_id() -> None:
    ext = aggregator_card_dedupe_id(
        aggregator_job_id="naukri:42",
        company_name="Acme",
        title="Dev",
        location="Remote",
    )
    assert ext == "naukri:42"


def test_listing_pagination_gate() -> None:
    ok, reason = listing_page_access("https://www.naukri.com/jobs?page=2", markdown="jobs")
    assert ok is False
    assert reason == "listing_pagination_gated"


def test_indeed_is_aggregator_with_detail_detection() -> None:
    assert is_aggregator_host("https://www.indeed.com/q-developer-jobs.html") is True
    view = "https://www.indeed.com/viewjob?jk=abc1234567890ab12"
    assert is_aggregator_job_detail_url(view) is True
    assert is_aggregator_listing_page(view) is False


def test_heuristic_job_board_host() -> None:
    assert is_aggregator_host("https://www.jooble.org/jobs-developer") is True


def test_rejects_nested_listing_card_url() -> None:
    assert (
        should_accept_card_job_url("https://www.indeed.com/q-developer-jobs.html")
        is False
    )


def test_completeness_cap_for_aggregator_provenance() -> None:
    job = Job(
        title="Frontend Developer",
        url="https://www.naukri.com/job-listings-x-123456789",
        description="Short",
        skills=["a"],
    )
    JobCompletenessService().apply_to_job(job, provenance="aggregator_listing")
    assert job.extraction_provenance == "aggregator_listing"
    assert job.completeness_score is not None
    assert job.completeness_score <= aggregator_listing_max_score()
