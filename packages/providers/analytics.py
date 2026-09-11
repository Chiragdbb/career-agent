"""AnalyticsProvider — product analytics without sensitive candidate data."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from packages.providers.base import MockBehavior, ProviderMetadata, TimeoutMixin, UsageInfo

logger = logging.getLogger("career.analytics")

_FORBIDDEN_KEYS = frozenset(
    {
        "resume",
        "resume_text",
        "plain_text",
        "email_body",
        "body",
        "body_html",
        "api_key",
        "password",
        "token",
        "oauth",
        "ssn",
        "phone",
    }
)


class AnalyticsEventName(str, Enum):
    signup = "signup"
    activation = "activation"
    profile_completed = "profile_completed"
    resume_uploaded = "resume_uploaded"
    job_discovered = "job_discovered"
    job_shortlisted = "job_shortlisted"
    application_prepared = "application_prepared"
    application_submitted = "application_submitted"
    outreach_sent = "outreach_sent"
    response_received = "response_received"
    interview_scheduled = "interview_scheduled"
    offer_received = "offer_received"


class AnalyticsTrackRequest(TimeoutMixin):
    event: AnalyticsEventName
    user_id: UUID | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class AnalyticsTrackResponse(BaseModel):
    accepted: bool
    usage: UsageInfo


class AnalyticsProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError

    @abstractmethod
    def track(self, request: AnalyticsTrackRequest) -> AnalyticsTrackResponse:
        raise NotImplementedError


def scrub_properties(properties: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in properties.items():
        lower = key.lower()
        if lower in _FORBIDDEN_KEYS or any(f in lower for f in _FORBIDDEN_KEYS):
            continue
        if isinstance(value, str) and len(value) > 500:
            cleaned[key] = value[:500]
        else:
            cleaned[key] = value
    return cleaned


class MockAnalyticsProvider(AnalyticsProvider):
    def __init__(self) -> None:
        self.events: list[AnalyticsTrackRequest] = []
        self._behavior = MockBehavior(provider_name="mock-analytics", latency_ms=1.0)
        self._meta = ProviderMetadata(
            name="mock-analytics",
            vendor="mock",
            capabilities=frozenset({"track"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def track(self, request: AnalyticsTrackRequest) -> AnalyticsTrackResponse:
        self._behavior.before_call(operation="track", timeout_seconds=request.timeout_seconds)
        scrubbed = AnalyticsTrackRequest(
            event=request.event,
            user_id=request.user_id,
            properties=scrub_properties(request.properties),
            timeout_seconds=request.timeout_seconds,
        )
        self.events.append(scrubbed)
        return AnalyticsTrackResponse(
            accepted=True,
            usage=self._behavior.usage(operation="track"),
        )


class PostHogAnalyticsProvider(AnalyticsProvider):
    """PostHog HTTP adapter. Never required for core product functionality."""

    def __init__(
        self,
        *,
        api_key: str,
        host: str = "https://app.posthog.com",
    ) -> None:
        self._api_key = api_key.strip()
        self._host = host.rstrip("/")
        self._meta = ProviderMetadata(
            name="posthog-analytics",
            vendor="posthog",
            capabilities=frozenset({"track"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def track(self, request: AnalyticsTrackRequest) -> AnalyticsTrackResponse:
        from packages.providers.http_utils import request_with_retries

        props = scrub_properties(request.properties)
        distinct_id = str(request.user_id) if request.user_id else "anonymous"
        body = {
            "api_key": self._api_key,
            "event": request.event.value,
            "properties": {
                **props,
                "distinct_id": distinct_id,
            },
        }
        response = request_with_retries(
            method="POST",
            url=f"{self._host}/capture/",
            provider=self._meta.name,
            operation="track",
            timeout_seconds=request.timeout_seconds,
            headers={"Content-Type": "application/json"},
            json=body,
        )
        return AnalyticsTrackResponse(
            accepted=response.status_code < 400,
            usage=UsageInfo(
                operation="track",
                unit_type="requests",
                units=1.0,
                provider=self._meta.name,
            ),
        )


def create_analytics_provider():
    import os

    key = (os.getenv("POSTHOG_API_KEY") or "").strip()
    if key:
        return PostHogAnalyticsProvider(
            api_key=key,
            host=(os.getenv("POSTHOG_HOST") or "https://app.posthog.com").strip(),
        )
    return MockAnalyticsProvider()
