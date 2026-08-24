"""EmailVerifierProvider — verify deliverability / validity of an address."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum

from pydantic import BaseModel, Field

from packages.providers.base import (
    MockBehavior,
    ProviderMetadata,
    TimeoutMixin,
    UsageInfo,
)


class EmailVerificationStatus(StrEnum):
    valid = "valid"
    invalid = "invalid"
    risky = "risky"
    unknown = "unknown"


class EmailVerifyRequest(TimeoutMixin):
    email: str = Field(min_length=3)


class EmailVerifyResponse(BaseModel):
    email: str
    status: EmailVerificationStatus
    score: float | None = None
    details: str | None = None
    usage: UsageInfo


class EmailVerifierProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError

    @abstractmethod
    def verify_email(self, request: EmailVerifyRequest) -> EmailVerifyResponse:
        raise NotImplementedError


class MockEmailVerifierProvider(EmailVerifierProvider):
    def __init__(
        self,
        *,
        status: EmailVerificationStatus = EmailVerificationStatus.valid,
        score: float = 0.95,
        fail_with: Exception | None = None,
        simulate_timeout: bool = False,
        latency_ms: float = 4.0,
    ) -> None:
        self._status = status
        self._score = score
        self._behavior = MockBehavior(
            fail_with=fail_with,
            simulate_timeout=simulate_timeout,
            latency_ms=latency_ms,
            provider_name="mock-email-verifier",
        )
        self._meta = ProviderMetadata(
            name="mock-email-verifier",
            vendor="mock",
            capabilities=frozenset({"email_verify"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def verify_email(self, request: EmailVerifyRequest) -> EmailVerifyResponse:
        self._behavior.before_call(
            operation="verify_email",
            timeout_seconds=request.timeout_seconds,
        )
        return EmailVerifyResponse(
            email=request.email,
            status=self._status,
            score=self._score,
            details="mock verification",
            usage=self._behavior.usage(operation="verify_email", unit_type="verifications", units=1.0),
        )
