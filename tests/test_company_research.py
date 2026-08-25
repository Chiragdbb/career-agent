"""STEP 15 — CompanyResearchService with mocked providers."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from database.models.enums import CompanyResearchStatus, CompanyStatus, UserStatus
from database.models.schema import Company, CompanyResearch, User
from packages.domain.company_research import CompanyResearchService, DEFAULT_FRESHNESS_DAYS
from packages.domain.llm_tasks import LLMTaskService
from packages.providers.llm import MockLLMProvider
from packages.providers.scraper import MockScraperProvider, ScrapedPage
from packages.providers.exceptions import ProviderUnavailableError
from packages.providers.search import MockSearchProvider, SearchHit


def _session():
    from app.database import get_session_factory

    return get_session_factory()()


@pytest.fixture
def research_ctx():
    session = _session()
    user = User(id=uuid.uuid4(), auth_subject=f"research-{uuid.uuid4()}", status=UserStatus.active)
    company = Company(
        id=uuid.uuid4(),
        name="Research Target Inc",
        url="https://research-target.example",
        status=CompanyStatus.active,
    )
    session.add_all([user, company])
    session.commit()
    try:
        yield session, user, company
    finally:
        session.query(CompanyResearch).filter(CompanyResearch.user_id == user.id).delete()
        session.query(Company).filter(Company.id == company.id).delete()
        session.query(User).filter(User.id == user.id).delete()
        session.commit()
        session.close()


def _service(session, user_id, *, search=None, scraper=None, llm=None, freshness_days=7):
    return CompanyResearchService(
        session,
        user_id,
        search=search
        or MockSearchProvider(fail_with=ProviderUnavailableError("no search results")),
        scraper=scraper or MockScraperProvider(pages=[]),
        llm_tasks=LLMTaskService(llm or MockLLMProvider()),
        freshness_days=freshness_days,
    )


def test_research_marks_unavailable_without_sources(research_ctx) -> None:
    session, user, company = research_ctx
    row = _service(session, user.id).research_company(company.id)
    assert row.status == CompanyResearchStatus.complete
    assert row.data["unavailable"] is True
    assert row.data["reason"] == "no_verifiable_sources"
    assert "unavailable" in (row.summary or "").lower()


def test_research_persists_validated_llm_output(research_ctx) -> None:
    session, user, company = research_ctx
    source_url = "https://research-target.example/about"
    llm_payload = json.dumps(
        {
            "company_name": company.name,
            "summary": "Research Target builds developer tools.",
            "industry": "Software",
            "size_hint": "51-200",
            "tech_stack": ["Python", "Postgres"],
            "sources_note": "Based on scraped about page only.",
        }
    )
    service = _service(
        session,
        user.id,
        search=MockSearchProvider(
            results=[SearchHit(title="About", url=source_url, snippet="tools", score=1.0)]
        ),
        scraper=MockScraperProvider(
            pages=[ScrapedPage(url=source_url, title="About", markdown="# About us\nDev tools.")]
        ),
        llm=MockLLMProvider(content=llm_payload),
    )
    row = service.research_company(company.id)
    assert row.status == CompanyResearchStatus.complete
    assert row.data["unavailable"] is False
    assert row.summary == "Research Target builds developer tools."
    assert row.data["tech_stack"] == ["Python", "Postgres"]
    assert source_url in row.data["sources"]


def test_research_uses_fresh_cache(research_ctx) -> None:
    session, user, company = research_ctx
    cached = CompanyResearch(
        id=uuid.uuid4(),
        user_id=user.id,
        company_id=company.id,
        status=CompanyResearchStatus.complete,
        summary="Cached summary",
        data={"unavailable": False, "sources": ["https://cached.example"]},
    )
    session.add(cached)
    session.commit()

    row = _service(
        session,
        user.id,
        search=MockSearchProvider(results=[SearchHit(title="x", url="https://x", snippet="", score=1)]),
    ).research_company(company.id)
    assert row.id == cached.id
    assert row.summary == "Cached summary"


def test_stale_research_is_refreshed(research_ctx) -> None:
    session, user, company = research_ctx
    stale_time = datetime.now(timezone.utc) - timedelta(days=DEFAULT_FRESHNESS_DAYS + 1)
    cached = CompanyResearch(
        id=uuid.uuid4(),
        user_id=user.id,
        company_id=company.id,
        status=CompanyResearchStatus.complete,
        summary="Old summary",
        data={"unavailable": False},
    )
    session.add(cached)
    session.commit()
    session.query(CompanyResearch).filter(CompanyResearch.id == cached.id).update(
        {"updated_at": stale_time.replace(tzinfo=None)},
        synchronize_session=False,
    )
    session.commit()

    source_url = "https://research-target.example/new"
    llm_payload = json.dumps(
        {
            "company_name": company.name,
            "summary": "Fresh summary",
            "industry": None,
            "size_hint": None,
            "tech_stack": [],
        }
    )
    row = _service(
        session,
        user.id,
        search=MockSearchProvider(
            results=[SearchHit(title="New", url=source_url, snippet="", score=1.0)]
        ),
        scraper=MockScraperProvider(
            pages=[ScrapedPage(url=source_url, title="New", markdown="# Fresh info")]
        ),
        llm=MockLLMProvider(content=llm_payload),
    ).research_company(company.id)
    assert row.id == cached.id
    assert row.summary == "Fresh summary"
    assert "industry" in row.data["unverified_fields"]
