"""Provider usage recording and quota enforcement."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from packages.domain.provider_usage import (
    ProviderQuotaLimits,
    ProviderUsageContext,
    ProviderUsageService,
    QuotaExceededError,
    UsageTrackingMiddleware,
)
from packages.providers.base import UsageInfo


def test_record_usage_flushes_row() -> None:
    session = MagicMock()
    service = ProviderUsageService(session)
    service.record(
        context=ProviderUsageContext(user_id=uuid.uuid4()),
        provider_name="mock-search",
        operation="search",
        usage=UsageInfo(operation="search", units=1.0, latency_ms=12.0),
        request_id="req-1",
    )
    assert session.add.called
    assert session.flush.called


def test_quota_reject() -> None:
    session = MagicMock()
    service = ProviderUsageService(session, limits=ProviderQuotaLimits(searches=1))
    service.usage_today = lambda user_id, key: 1.0  # type: ignore[method-assign]
    with pytest.raises(QuotaExceededError) as exc:
        service.check_quota(uuid.uuid4(), "search")
    assert exc.value.action == "reject"
    assert exc.value.quota_key == "searches"


def test_usage_middleware_before_after() -> None:
    session = MagicMock()
    usage = ProviderUsageService(session, limits=ProviderQuotaLimits(searches=10))
    usage.usage_today = lambda user_id, key: 0.0  # type: ignore[method-assign]
    mw = UsageTrackingMiddleware(
        usage, ProviderUsageContext(user_id=uuid.uuid4())
    )
    mw.before("search")
    mw.after(
        provider_name="mock",
        operation="search",
        usage=UsageInfo(operation="search"),
    )
    assert session.add.called
