"""Tests for tiered scraping pipeline + contact enrichment + usage reporting."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from packages.domain.contacts import ContactEnrichmentService, contact_staleness_days
from packages.domain.job_normalize import normalize_job_posting, structured_to_extracted
from packages.domain.job_posting import StructuredJobPosting
from packages.domain.provider_usage import (
    ProviderUsageContext,
    ProviderUsageService,
)
from packages.providers.base import UsageInfo
from packages.providers.exceptions import ProviderValidationError
from packages.providers.firecrawl_scraper import FirecrawlScraperProvider
from packages.providers.playwright_contacts import (
    MockPlaywrightContactsProvider,
    ScrapedContactHit,
    assert_company_owned_url,
    parse_team_page_text,
)
from packages.providers.playwright_jobs import (
    MockPlaywrightJobsProvider,
    is_known_job_board,
    match_job_source,
    parse_greenhouse_dom,
)
from packages.providers.usage_logging import call_with_usage_log


def _sample_posting(**overrides: object) -> StructuredJobPosting:
    base = {
        "external_job_id": "12345",
        "source": "playwright",
        "company_name": "Acme",
        "company_domain": "acme.com",
        "title": "Software Engineer",
        "description": "Build APIs with Python and SQL.",
        "requirements": ["3+ years Python"],
        "skills": ["Python", "SQL"],
        "location": "Remote",
        "remote_type": "remote",
        "employment_type": "full_time",
        "seniority": "mid",
        "salary_min": 100000,
        "salary_max": 140000,
        "salary_currency": "USD",
        "application_url": "https://boards.greenhouse.io/acme/jobs/12345",
        "posted_at": None,
        "scraped_at": datetime.now(timezone.utc),
    }
    base.update(overrides)
    return StructuredJobPosting.model_validate(base)


def test_normalize_job_posting_accepts_schema() -> None:
    posting = normalize_job_posting(_sample_posting())
    assert posting.external_job_id == "12345"
    assert posting.source == "playwright"
    assert "Python" in posting.skills


def test_structured_to_extracted_maps_remote() -> None:
    extracted = structured_to_extracted(_sample_posting(remote_type="onsite"))
    assert extracted.work_arrangement == "on_site"
    assert extracted.external_id == "12345"


def test_llm_payload_excludes_html() -> None:
    payload = _sample_posting().to_llm_payload()
    assert "html" not in payload
    assert "description" in payload
    assert payload["source"] == "playwright"


def test_greenhouse_parser_returns_schema() -> None:
    url = "https://boards.greenhouse.io/acme/jobs/999"
    posting = parse_greenhouse_dom(
        {
            "title": "Backend Engineer",
            "description": "Work with Python and Docker. Requirements: 5 years.",
            "location": "Hybrid - NYC",
            "company_name": "Acme Corp",
        },
        url=url,
    )
    assert posting.external_job_id == "999"
    assert posting.source == "playwright"
    assert posting.remote_type == "hybrid"
    assert "Python" in posting.skills


def test_known_board_detection() -> None:
    assert is_known_job_board("https://boards.greenhouse.io/x/jobs/1")
    assert match_job_source("https://linkedin.com/jobs/view/1") is None


def test_mock_playwright_jobs_scrape() -> None:
    provider = MockPlaywrightJobsProvider()
    result = provider.scrape_job("https://boards.greenhouse.io/acme/jobs/42")
    assert result.posting.source == "playwright"
    assert result.usage.provider == "mock-playwright-jobs"


def test_firecrawl_refuses_known_boards() -> None:
    provider = FirecrawlScraperProvider(base_url="http://localhost:3002")
    with pytest.raises(ProviderValidationError):
        provider.extract_structured_job("https://boards.greenhouse.io/acme/jobs/1")


def test_contacts_block_linkedin() -> None:
    with pytest.raises(ProviderValidationError):
        assert_company_owned_url("https://www.linkedin.com/in/someone", "acme.com")


def test_parse_team_page_extracts_names() -> None:
    text = "Jane Doe - Head of Recruiting\nJohn Smith, Engineering Manager\nreach us at talent@acme.com"
    hits = parse_team_page_text(text, source_url="https://acme.com/team", company_domain="acme.com")
    assert any(h.full_name == "Jane Doe" for h in hits)


def test_find_or_enrich_uses_cache_then_playwright() -> None:
    session = MagicMock()
    company = MagicMock()
    company.id = uuid.uuid4()
    company.name = "Acme"
    company.url = "https://acme.com"

    contact = MagicMock()
    contact.name = "Cached Person"
    contact.title = "Recruiter"
    contact.last_verified_at = datetime.now(timezone.utc)
    contact.updated_at = datetime.now(timezone.utc)

    session.query.return_value.filter.return_value.one_or_none.return_value = company
    # Fresh cache path: query Contact returns list via order_by().all()
    contact_query = MagicMock()
    contact_query.filter.return_value.order_by.return_value.all.return_value = [contact]

    def query_side_effect(model):
        from database.models.schema import Company, Contact

        if model is Company:
            q = MagicMock()
            q.filter.return_value.one_or_none.return_value = company
            return q
        if model is Contact:
            return contact_query
        return MagicMock()

    session.query.side_effect = query_side_effect

    service = ContactEnrichmentService(
        session,
        uuid.uuid4(),
        playwright_contacts=MockPlaywrightContactsProvider(),
        usage=ProviderUsageService(session),
    )
    result = service.find_or_enrich_contact(company.id)
    assert result.cache_hit is True
    assert result.tier == "cache"


def test_find_or_enrich_playwright_tier() -> None:
    session = MagicMock()
    company_id = uuid.uuid4()
    company = MagicMock()
    company.id = company_id
    company.name = "Acme"
    company.url = "https://acme.com"

    domain_row = MagicMock()
    domain_row.domain = "acme.com"

    def query_side_effect(model):
        from database.models.schema import Company, CompanyDomain, Contact

        q = MagicMock()
        if model is Company:
            q.filter.return_value.one_or_none.return_value = company
            return q
        if model is Contact:
            q.filter.return_value.order_by.return_value.all.return_value = []
            return q
        if model is CompanyDomain:
            q.filter.return_value.order_by.return_value.first.return_value = domain_row
            return q
        return q

    session.query.side_effect = query_side_effect

    pw = MockPlaywrightContactsProvider(
        contacts=[
            ScrapedContactHit(
                full_name="Pat Recruiter",
                title="Talent",
                email="pat@acme.com",
                email_confidence="verified",
                source_url="https://acme.com/team",
            )
        ]
    )
    service = ContactEnrichmentService(
        session,
        uuid.uuid4(),
        playwright_contacts=pw,
        usage=ProviderUsageService(session),
    )
    result = service.find_or_enrich_contact(company_id)
    assert result.tier == "playwright"
    assert result.cache_hit is False
    assert session.add.called


def test_call_with_usage_log_records_failure() -> None:
    session = MagicMock()
    usage = ProviderUsageService(session)
    context = ProviderUsageContext(user_id=uuid.uuid4())

    def boom() -> None:
        raise RuntimeError("provider down")

    with pytest.raises(RuntimeError):
        call_with_usage_log(
            usage,
            context=context,
            provider="mock",
            operation="job_extraction",
            fn=boom,
        )
    assert session.add.call_count >= 1
    row = session.add.call_args[0][0]
    assert row.success is False
    assert row.error_code == "RuntimeError"


def test_efficiency_report_shape() -> None:
    session = MagicMock()
    row = MagicMock()
    row.operation = "contact_lookup"
    row.success = True
    row.provider_name = "db-cache"
    row.payload = {"tier": "cache", "cache_hit": True}
    row.cost_estimate = 0.0
    row.requests_count = 1
    row.token_count = 0
    row.tokens_input = None
    row.tokens_output = None
    row.credit_count = 1
    row.created_at = datetime.now(timezone.utc)

    job_row = MagicMock()
    job_row.operation = "job_extraction"
    job_row.success = True
    job_row.provider_name = "playwright-jobs"
    job_row.payload = {}
    job_row.cost_estimate = 0.0
    job_row.requests_count = 1
    job_row.token_count = 0
    job_row.tokens_input = None
    job_row.tokens_output = None
    job_row.credit_count = 1
    job_row.created_at = datetime.now(timezone.utc)

    session.query.return_value.filter.return_value.all.return_value = [row, job_row]
    report = ProviderUsageService(session).efficiency_report()
    assert "contact_cache_hit_rate" in report
    assert "job_scraper_split" in report
    assert "free_tier_headroom" in report
    assert report["job_scraper_split"]["playwright"] == 1


def test_contact_staleness_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTACT_STALENESS_DAYS", "90")
    assert contact_staleness_days() == 90
