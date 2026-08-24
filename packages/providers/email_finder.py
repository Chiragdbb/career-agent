"""EmailFinderProvider — discover likely work emails.

Never invent an email address in business logic; finder results are unverified
suggestions until EmailVerifierProvider confirms them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from packages.providers.base import (
    MockBehavior,
    ProviderMetadata,
    TimeoutMixin,
    UsageInfo,
)


class EmailFindRequest(TimeoutMixin):
    full_name: str = Field(min_length=1)
    company_domain: str = Field(min_length=1)
    company_name: str | None = None


class EmailCandidate(BaseModel):
    email: str = Field(min_length=3)
    confidence: float = Field(ge=0.0, le=1.0)
    sources: list[str] = Field(default_factory=list)


class EmailFindResponse(BaseModel):
    candidates: list[EmailCandidate]
    usage: UsageInfo


class EmailFinderProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError

    @abstractmethod
    def find_email(self, request: EmailFindRequest) -> EmailFindResponse:
        raise NotImplementedError


class MockEmailFinderProvider(EmailFinderProvider):
    def __init__(
        self,
        *,
        candidates: list[EmailCandidate] | None = None,
        fail_with: Exception | None = None,
        simulate_timeout: bool = False,
        latency_ms: float = 6.0,
    ) -> None:
        self._candidates = candidates or [
            EmailCandidate(email="alex.mock@example.com", confidence=0.8, sources=["mock"])
        ]
        self._behavior = MockBehavior(
            fail_with=fail_with,
            simulate_timeout=simulate_timeout,
            latency_ms=latency_ms,
            provider_name="mock-email-finder",
        )
        self._meta = ProviderMetadata(
            name="mock-email-finder",
            vendor="mock",
            capabilities=frozenset({"email_find"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def find_email(self, request: EmailFindRequest) -> EmailFindResponse:
        self._behavior.before_call(operation="find_email", timeout_seconds=request.timeout_seconds)
        return EmailFindResponse(
            candidates=list(self._candidates),
            usage=self._behavior.usage(operation="find_email", unit_type="lookups", units=1.0),
        )
