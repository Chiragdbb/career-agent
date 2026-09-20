"""Persist provider call usage and enforce per-user quotas."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models.schema import ProviderUsage
from packages.domain.exceptions import DomainError
from packages.providers.base import UsageInfo

logger = logging.getLogger("career.provider_usage")


class QuotaExceededError(DomainError):
    """User or global provider quota would be exceeded."""

    def __init__(
        self,
        message: str,
        *,
        quota_key: str,
        used: float,
        limit: float,
        action: str = "reject",
    ) -> None:
        super().__init__(message)
        self.quota_key = quota_key
        self.used = used
        self.limit = limit
        self.action = action  # reject | defer | queue


class QuotaAction(str, Enum):
    reject = "reject"
    defer = "defer"
    queue = "queue"


class ProviderQuotaLimits(BaseModel):
    """Daily per-user quotas for third-party operations."""

    searches: int = Field(default=100, ge=0)
    scraped_pages: int = Field(default=200, ge=0)
    company_research: int = Field(default=50, ge=0)
    contacts: int = Field(default=100, ge=0)
    applications: int = Field(default=30, ge=0)
    emails: int = Field(default=50, ge=0)
    llm_tokens: int = Field(default=500_000, ge=0)
    embeddings: int = Field(default=200, ge=0)


_OPERATION_QUOTA_MAP: dict[str, str] = {
    "search": "searches",
    "scrape": "scraped_pages",
    "crawl": "scraped_pages",
    "research_company": "company_research",
    "people_search": "contacts",
    "find_email": "contacts",
    "verify_email": "contacts",
    "send_email": "emails",
    "complete": "llm_tokens",
    "embed": "embeddings",
}


@dataclass(frozen=True)
class ProviderUsageContext:
    user_id: uuid.UUID | None = None
    workflow_run_id: uuid.UUID | None = None
    workflow_task_id: uuid.UUID | None = None


# Known free-tier request ceilings for early-warning reporting (§4.4).
FREE_TIER_CEILINGS: dict[str, dict[str, float]] = {
    "groq": {"requests_per_day": 1000, "tokens_per_day": 500_000},
    "gemini": {"requests_per_day": 1500, "tokens_per_day": 1_000_000},
    "firecrawl-scraper": {"requests_per_day": 500, "credits_per_day": 500},
    "playwright-jobs": {"requests_per_day": 10_000},
    "playwright-contacts": {"requests_per_day": 10_000},
}


class ProviderUsageService:
    """Write normalized provider usage rows and enforce daily quotas."""

    def __init__(
        self,
        session: Session,
        *,
        limits: ProviderQuotaLimits | None = None,
        on_exceed: QuotaAction = QuotaAction.reject,
    ) -> None:
        self._session = session
        self._limits = limits or ProviderQuotaLimits()
        self._on_exceed = on_exceed

    def record(
        self,
        *,
        context: ProviderUsageContext,
        provider_name: str,
        operation: str,
        usage: UsageInfo,
        success: bool = True,
        error: str | None = None,
        request_id: str | None = None,
        related_entity_type: str | None = None,
        related_entity_id: uuid.UUID | None = None,
        tokens_input: int | None = None,
        tokens_output: int | None = None,
        error_code: str | None = None,
    ) -> None:
        token_count: int | None = None
        if usage.unit_type == "tokens":
            token_count = int(usage.units)

        credit_count: float | None = None
        if usage.unit_type in ("requests", "credits", "pages"):
            credit_count = float(usage.units)

        payload: dict[str, Any] = dict(usage.extra)
        payload["unit_type"] = usage.unit_type
        if request_id:
            payload["request_id"] = request_id
        elif usage.extra.get("request_id"):
            payload["request_id"] = usage.extra["request_id"]
        payload["recorded_at"] = datetime.now(timezone.utc).isoformat()

        extra_tokens_in = tokens_input
        extra_tokens_out = tokens_output
        if extra_tokens_in is None and isinstance(usage.extra.get("tokens_input"), int):
            extra_tokens_in = usage.extra["tokens_input"]
        if extra_tokens_out is None and isinstance(usage.extra.get("tokens_output"), int):
            extra_tokens_out = usage.extra["tokens_output"]

        row = ProviderUsage(
            user_id=context.user_id,
            workflow_run_id=context.workflow_run_id,
            workflow_task_id=context.workflow_task_id,
            provider_name=provider_name,
            operation=operation,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            token_count=token_count,
            tokens_input=extra_tokens_in,
            tokens_output=extra_tokens_out,
            requests_count=1,
            credit_count=credit_count,
            cost_estimate=usage.estimated_cost_usd,
            latency_ms=int(usage.latency_ms) if usage.latency_ms is not None else None,
            success=success,
            error=error,
            error_code=error_code or (None if success else "provider_error"),
            payload=payload,
        )
        self._session.add(row)
        try:
            self._session.flush()
        except Exception:
            logger.warning("provider_usage_record_failed", exc_info=True)

    def check_quota(
        self,
        user_id: uuid.UUID,
        operation: str,
        *,
        units: float = 1.0,
    ) -> None:
        """Raise QuotaExceededError when the daily limit would be exceeded."""
        quota_key = _OPERATION_QUOTA_MAP.get(operation)
        if quota_key is None:
            return
        limit = float(getattr(self._limits, quota_key))
        if limit <= 0:
            raise QuotaExceededError(
                f"Quota disabled for {quota_key}",
                quota_key=quota_key,
                used=0,
                limit=limit,
                action=self._on_exceed.value,
            )
        used = self.usage_today(user_id, quota_key)
        if used + units > limit:
            raise QuotaExceededError(
                f"Daily {quota_key} quota exceeded ({used}/{limit})",
                quota_key=quota_key,
                used=used,
                limit=limit,
                action=self._on_exceed.value,
            )

    def usage_today(self, user_id: uuid.UUID, quota_key: str) -> float:
        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        operations = [op for op, key in _OPERATION_QUOTA_MAP.items() if key == quota_key]
        if not operations:
            return 0.0
        query = (
            self._session.query(ProviderUsage)
            .filter(
                ProviderUsage.user_id == user_id,
                ProviderUsage.operation.in_(operations),
                ProviderUsage.created_at >= start,
                ProviderUsage.success.is_(True),
            )
        )
        if quota_key == "llm_tokens":
            total = query.with_entities(func.coalesce(func.sum(ProviderUsage.token_count), 0)).scalar()
            return float(total or 0)
        return float(query.count())

    def summarize_today(self, user_id: uuid.UUID) -> dict[str, float]:
        return {
            key: self.usage_today(user_id, key)
            for key in (
                "searches",
                "scraped_pages",
                "company_research",
                "contacts",
                "applications",
                "emails",
                "llm_tokens",
                "embeddings",
            )
        }

    def summarize_workflow_run(
        self,
        *,
        workflow_run_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Aggregate provider usage for one workflow run (for discovery summary.json)."""
        rows = (
            self._session.query(ProviderUsage)
            .filter(ProviderUsage.workflow_run_id == workflow_run_id)
            .all()
        )
        by_provider: dict[str, dict[str, float]] = {}
        for row in rows:
            bucket = by_provider.setdefault(row.provider_name, {})
            if row.token_count:
                bucket["tokens"] = bucket.get("tokens", 0.0) + float(row.token_count)
            if row.tokens_input:
                bucket["prompt_tokens"] = bucket.get("prompt_tokens", 0.0) + float(
                    row.tokens_input
                )
            if row.tokens_output:
                bucket["completion_tokens"] = bucket.get("completion_tokens", 0.0) + float(
                    row.tokens_output
                )
            unit = (row.payload or {}).get("unit_type") if isinstance(row.payload, dict) else None
            if unit == "searches" or row.operation == "search":
                bucket["searches"] = bucket.get("searches", 0.0) + 1.0
            elif unit in ("pages", "credits") or row.operation in ("scrape", "crawl"):
                bucket["pages"] = bucket.get("pages", 0.0) + float(row.credit_count or 1)
            bucket["requests"] = bucket.get("requests", 0.0) + float(row.requests_count or 1)

        quota: dict[str, dict[str, float]] = {}
        if user_id is not None:
            today = self.summarize_today(user_id)
            limits = self._limits
            for key, used in today.items():
                quota[key] = {
                    "used": used,
                    "limit": float(getattr(limits, key)),
                }
        return {"by_provider": by_provider, "quota": quota}

    def efficiency_report(
        self,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> dict[str, Any]:
        """Aggregate cache hit rate, tier fallback, scraper split, and free-tier headroom."""
        until = until or datetime.now(timezone.utc)
        since = since or (until - timedelta(days=7))

        rows = (
            self._session.query(ProviderUsage)
            .filter(
                ProviderUsage.created_at >= since,
                ProviderUsage.created_at < until,
            )
            .all()
        )

        contact_lookups = [r for r in rows if r.operation == "contact_lookup"]
        cache_hits = sum(
            1
            for r in contact_lookups
            if r.success
            and isinstance(r.payload, dict)
            and r.payload.get("tier") == "cache"
            and r.payload.get("cache_hit")
        )
        playwright_contacts = sum(
            1
            for r in contact_lookups
            if r.success
            and (
                (isinstance(r.payload, dict) and r.payload.get("tier") == "playwright")
                or "playwright" in (r.provider_name or "")
            )
        )
        paid_contacts = sum(
            1
            for r in contact_lookups
            if r.success
            and isinstance(r.payload, dict)
            and r.payload.get("tier") in ("apollo", "hunter", "contactout")
        )
        contact_success = sum(1 for r in contact_lookups if r.success)
        cache_hit_rate = (cache_hits / contact_success) if contact_success else None
        paid_fallback_rate = (paid_contacts / contact_success) if contact_success else None

        job_extractions = [r for r in rows if r.operation in ("job_extraction", "scrape", "scrape_cached")]
        pw_jobs = sum(1 for r in job_extractions if "playwright" in (r.provider_name or ""))
        fc_jobs = sum(1 for r in job_extractions if "firecrawl" in (r.provider_name or ""))
        scraper_total = pw_jobs + fc_jobs

        cost_rows = [r for r in rows if r.cost_estimate is not None]
        total_cost = sum(float(r.cost_estimate or 0) for r in cost_rows)
        jobs_processed = max(scraper_total, 1)
        contacts_resolved = max(contact_success, 1)

        by_provider: dict[str, dict[str, float]] = {}
        for r in rows:
            bucket = by_provider.setdefault(
                r.provider_name,
                {"requests": 0, "tokens": 0, "credits": 0, "cost_usd": 0.0, "failures": 0},
            )
            bucket["requests"] += float(r.requests_count or 1)
            bucket["tokens"] += float(r.token_count or 0) + float(r.tokens_input or 0) + float(
                r.tokens_output or 0
            )
            bucket["credits"] += float(r.credit_count or 0)
            bucket["cost_usd"] += float(r.cost_estimate or 0)
            if not r.success:
                bucket["failures"] += 1

        free_tier: dict[str, Any] = {}
        for provider, ceilings in FREE_TIER_CEILINGS.items():
            used = by_provider.get(provider, {"requests": 0, "tokens": 0, "credits": 0})
            free_tier[provider] = {
                "used_requests": used["requests"],
                "used_tokens": used["tokens"],
                "ceilings": ceilings,
                "requests_pct": (
                    used["requests"] / ceilings["requests_per_day"]
                    if ceilings.get("requests_per_day")
                    else None
                ),
            }

        return {
            "since": since.isoformat(),
            "until": until.isoformat(),
            "contact_cache_hit_rate": cache_hit_rate,
            "contact_playwright_successes": playwright_contacts,
            "contact_paid_fallback_rate": paid_fallback_rate,
            "job_scraper_split": {
                "playwright": pw_jobs,
                "firecrawl": fc_jobs,
                "playwright_pct": (pw_jobs / scraper_total) if scraper_total else None,
            },
            "cost_per_job_usd": total_cost / jobs_processed,
            "cost_per_contact_usd": total_cost / contacts_resolved,
            "by_provider": by_provider,
            "free_tier_headroom": free_tier,
        }


class UsageTrackingMiddleware:
    """Thin helper for provider factory / workers to check + record usage."""

    def __init__(self, usage: ProviderUsageService, context: ProviderUsageContext) -> None:
        self._usage = usage
        self._context = context

    def before(self, operation: str, *, units: float = 1.0) -> None:
        self._usage.check_quota(self._context.user_id, operation, units=units)

    def after(
        self,
        *,
        provider_name: str,
        operation: str,
        usage: UsageInfo,
        success: bool = True,
        error: str | None = None,
    ) -> None:
        self._usage.record(
            context=self._context,
            provider_name=provider_name,
            operation=operation,
            usage=usage,
            success=success,
            error=error,
        )
