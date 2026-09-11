"""Analytics + Notion optional providers (mock-safe)."""

from __future__ import annotations

import uuid

from packages.providers.analytics import (
    AnalyticsEventName,
    AnalyticsTrackRequest,
    MockAnalyticsProvider,
    scrub_properties,
)
from packages.providers.notion import (
    MockNotionProvider,
    NotionExportKind,
    NotionExportRequest,
)


def test_analytics_scrubs_sensitive_fields() -> None:
    cleaned = scrub_properties(
        {"resume_text": "SECRET", "job_id": "abc", "score": 0.9}
    )
    assert "resume_text" not in cleaned
    assert cleaned["job_id"] == "abc"


def test_mock_analytics_track() -> None:
    provider = MockAnalyticsProvider()
    resp = provider.track(
        AnalyticsTrackRequest(
            event=AnalyticsEventName.resume_uploaded,
            user_id=uuid.uuid4(),
            properties={"resume": "should-drop", "bytes": 12},
        )
    )
    assert resp.accepted
    assert "resume" not in provider.events[0].properties


def test_notion_disconnected_is_noop() -> None:
    provider = MockNotionProvider(connected=False)
    resp = provider.export_rows(
        NotionExportRequest(
            kind=NotionExportKind.jobs,
            user_id=uuid.uuid4(),
            items=[{"id": "1"}],
        )
    )
    assert resp.disconnected is True
    assert resp.exported == 0
    assert resp.skipped == 1
