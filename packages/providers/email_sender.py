"""EmailSenderProvider — outbound email delivery.

External communication must still require user approval at the service layer.
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


class EmailSendRequest(TimeoutMixin):
    to: list[str] = Field(min_length=1)
    subject: str = Field(min_length=1)
    body_text: str = ""
    body_html: str | None = None
    from_email: str | None = None
    reply_to: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)


class EmailSendResponse(BaseModel):
    message_id: str
    accepted: list[str]
    usage: UsageInfo


class EmailSenderProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError

    @abstractmethod
    def send_email(self, request: EmailSendRequest) -> EmailSendResponse:
        raise NotImplementedError


class MockEmailSenderProvider(EmailSenderProvider):
    def __init__(
        self,
        *,
        fail_with: Exception | None = None,
        simulate_timeout: bool = False,
        latency_ms: float = 5.0,
    ) -> None:
        self.sent: list[EmailSendRequest] = []
        self._behavior = MockBehavior(
            fail_with=fail_with,
            simulate_timeout=simulate_timeout,
            latency_ms=latency_ms,
            provider_name="mock-email-sender",
        )
        self._meta = ProviderMetadata(
            name="mock-email-sender",
            vendor="mock",
            capabilities=frozenset({"send_email"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def send_email(self, request: EmailSendRequest) -> EmailSendResponse:
        self._behavior.before_call(operation="send_email", timeout_seconds=request.timeout_seconds)
        self.sent.append(request)
        return EmailSendResponse(
            message_id=f"mock-msg-{len(self.sent)}",
            accepted=list(request.to),
            usage=self._behavior.usage(operation="send_email", unit_type="emails", units=float(len(request.to))),
        )
