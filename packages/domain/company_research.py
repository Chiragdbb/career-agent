"""Company research: search → scrape → LLM → persist with freshness cache."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from database.models.enums import CompanyResearchStatus
from database.models.schema import Company, CompanyResearch, Job
from packages.domain.exceptions import DomainError, NotFoundError
from packages.domain.llm_tasks import LLMTaskService
from packages.providers.scraper import ScrapeRequest, ScraperProvider
from packages.providers.search import SearchProvider, SearchRequest

DEFAULT_FRESHNESS_DAYS = 7
MAX_SOURCE_PAGES = 3


class CompanyResearchService:
    """Research a company for one tenant using provider interfaces only."""

    def __init__(
        self,
        session: Session,
        user_id: uuid.UUID,
        *,
        search: SearchProvider,
        scraper: ScraperProvider,
        llm_tasks: LLMTaskService,
        freshness_days: int = DEFAULT_FRESHNESS_DAYS,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._search = search
        self._scraper = scraper
        self._llm_tasks = llm_tasks
        self._freshness = timedelta(days=freshness_days)

    def research_for_job(
        self,
        job_id: uuid.UUID,
        *,
        force_refresh: bool = False,
    ) -> CompanyResearch:
        job = self._session.query(Job).filter(Job.id == job_id).one_or_none()
        if job is None:
            raise NotFoundError("Job not found")
        return self.research_company(job.company_id, force_refresh=force_refresh)

    def research_company(
        self,
        company_id: uuid.UUID,
        *,
        force_refresh: bool = False,
    ) -> CompanyResearch:
        company = self._session.query(Company).filter(Company.id == company_id).one_or_none()
        if company is None:
            raise NotFoundError("Company not found")

        cached = self._latest_research(company_id)
        if cached is not None and not force_refresh and not self._is_stale(cached):
            return cached

        row = cached if cached is not None else CompanyResearch(
            id=uuid.uuid4(),
            user_id=self._user_id,
            company_id=company_id,
            status=CompanyResearchStatus.in_progress,
        )
        if cached is None:
            self._session.add(row)
        else:
            row.status = CompanyResearchStatus.in_progress
            row.summary = None
            row.data = None
        self._session.flush()

        context, sources, scrape_errors = self._gather_context(company)
        if not context.strip():
            row.status = CompanyResearchStatus.complete
            row.summary = "Research unavailable — no verifiable sources could be retrieved."
            row.data = {
                "unavailable": True,
                "reason": "no_verifiable_sources",
                "sources": sources,
                "scrape_errors": scrape_errors,
                "researched_at": datetime.now(timezone.utc).isoformat(),
            }
            self._session.commit()
            self._session.refresh(row)
            return row

        try:
            result = self._llm_tasks.research_company(
                company_name=company.name,
                context=context,
            )
        except DomainError as exc:
            row.status = CompanyResearchStatus.complete
            row.summary = "Research unavailable — could not validate extracted company facts."
            row.data = {
                "unavailable": True,
                "reason": "llm_validation_failed",
                "error": str(exc),
                "sources": sources,
                "researched_at": datetime.now(timezone.utc).isoformat(),
            }
            self._session.commit()
            self._session.refresh(row)
            return row

        unverified_fields = []
        if result.industry is None:
            unverified_fields.append("industry")
        if result.size_hint is None:
            unverified_fields.append("size_hint")
        if not result.tech_stack:
            unverified_fields.append("tech_stack")

        row.status = CompanyResearchStatus.complete
        row.summary = result.summary
        row.data = {
            "company_name": result.company_name,
            "industry": result.industry,
            "size_hint": result.size_hint,
            "tech_stack": result.tech_stack,
            "sources_note": result.sources_note,
            "sources": sources,
            "unverified_fields": unverified_fields,
            "unavailable": False,
            "researched_at": datetime.now(timezone.utc).isoformat(),
            "prompt_version": self._llm_tasks.prompt_version,
        }
        self._session.commit()
        self._session.refresh(row)
        return row

    def get_research(self, company_id: uuid.UUID) -> CompanyResearch | None:
        return self._latest_research(company_id)

    def _latest_research(self, company_id: uuid.UUID) -> CompanyResearch | None:
        return (
            self._session.query(CompanyResearch)
            .filter(
                CompanyResearch.user_id == self._user_id,
                CompanyResearch.company_id == company_id,
            )
            .order_by(CompanyResearch.updated_at.desc())
            .first()
        )

    def _is_stale(self, row: CompanyResearch) -> bool:
        if row.status == CompanyResearchStatus.stale:
            return True
        if row.status != CompanyResearchStatus.complete:
            return True
        updated = row.updated_at or row.created_at
        if updated is None:
            return True
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - updated > self._freshness

    def _gather_context(self, company: Company) -> tuple[str, list[str], list[str]]:
        query = f"{company.name} company overview"
        if company.url:
            query += f" site:{company.url}"
        try:
            response = self._search.search(SearchRequest(query=query, max_results=MAX_SOURCE_PAGES))
        except Exception as exc:
            return "", [], [f"search:{exc}"]

        parts: list[str] = []
        sources: list[str] = []
        errors: list[str] = []
        for hit in response.results[:MAX_SOURCE_PAGES]:
            url = str(hit.url)
            sources.append(url)
            try:
                scraped = self._scraper.scrape_url(ScrapeRequest(url=url))
                markdown = (scraped.markdown or scraped.title or "").strip()
                if markdown:
                    parts.append(f"SOURCE: {url}\n{markdown[:8000]}")
            except Exception as exc:
                errors.append(f"scrape:{url}:{exc}")
        return "\n\n".join(parts), sources, errors
