"""Spec pipeline: composite search, completeness, JSON-LD, ATS extractors."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from packages.domain.job_ingest.completeness import JobCompletenessService
from packages.domain.job_ingest.json_ld import extract_job_posting_json_ld
from packages.domain.job_posting import StructuredJobPosting
from packages.providers.exceptions import ProviderError
from packages.providers.search import SearchHit, SearchRequest
from packages.providers.composite_search import CompositeSearchProvider
from packages.providers.serper_search import SerperSearchProvider


def _full_posting(**overrides: object) -> StructuredJobPosting:
    base = {
        "external_job_id": "1",
        "source": "json_ld",
        "company_name": "Acme",
        "company_domain": "acme.com",
        "title": "Engineer",
        "description": "x" * 130,
        "requirements": [],
        "skills": ["Python", "SQL"],
        "location": "Remote",
        "remote_type": "remote",
        "employment_type": "full_time",
        "seniority": "mid",
        "salary_min": 100000,
        "salary_max": 120000,
        "salary_currency": "USD",
        "application_url": "https://example.com/jobs/1",
        "posted_at": datetime.now(timezone.utc).date(),
        "scraped_at": datetime.now(timezone.utc),
    }
    base.update(overrides)
    return StructuredJobPosting.model_validate(base)


def test_completeness_scores_full_posting_high() -> None:
    posting = _full_posting()
    result = JobCompletenessService().score_posting(posting)
    assert result.score >= 85
    assert not result.missing_fields


def test_completeness_scores_sparse_posting_low() -> None:
    posting = _full_posting(
        skills=[],
        salary_min=None,
        salary_max=None,
        posted_at=None,
        description="short",
        location="TBD",
        remote_type=None,
    )
    result = JobCompletenessService().score_posting(posting)
    assert result.score < 55
    assert "skills" in result.missing_fields


def test_json_ld_extracts_job_posting() -> None:
    html = """
    <html><head>
    <script type="application/ld+json">
    {"@type":"JobPosting","title":"Backend Engineer","description":"Build APIs",
     "hiringOrganization":{"name":"Acme Corp"},
     "jobLocation":{"@type":"Place","address":{"addressLocality":"NYC"}},
     "datePosted":"2026-01-15"}
    </script></head><body></body></html>
    """
    posting = extract_job_posting_json_ld(html, url="https://acme.com/jobs/1")
    assert posting is not None
    assert posting.title == "Backend Engineer"
    assert posting.company_name == "Acme Corp"
    assert posting.source == "json_ld"


def test_composite_search_dedupes_and_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    class OkProvider:
        @property
        def metadata(self):
            m = MagicMock()
            m.name = "ok-search"
            m.vendor = "ok"
            return m

        def search(self, request: SearchRequest):
            from packages.providers.base import UsageInfo
            from packages.providers.search import SearchResponse

            return SearchResponse(
                results=[
                    SearchHit(title="A", url="https://boards.greenhouse.io/x/jobs/1", snippet=""),
                ],
                usage=UsageInfo(operation="search", unit_type="searches", units=1.0, provider="ok-search"),
            )

    class FailProvider:
        @property
        def metadata(self):
            m = MagicMock()
            m.name = "fail-search"
            m.vendor = "fail"
            return m

        def search(self, request: SearchRequest):
            raise ProviderError("quota", provider="fail-search", operation="search")

    composite = CompositeSearchProvider([FailProvider(), OkProvider()])  # type: ignore[list-item]
    resp = composite.search(SearchRequest(query="engineer", max_results=5))
    assert len(resp.results) == 1
    assert "greenhouse" in str(resp.results[0].url)


def test_serper_requires_key() -> None:
    with pytest.raises(Exception):
        SerperSearchProvider(api_key="")
