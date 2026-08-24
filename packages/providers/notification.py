"""NotificationProvider — user-facing notifications (in-app / email / push)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from packages.providers.base import (
    MockBehavior,
    ProviderMetadata,
    TimeoutMixin,
    UsageInfo,
)


class NotificationChannel(StrEnum):
    in_app = "in_app"
    email = "email"
    push = "push"


class NotificationSendRequest(TimeoutMixin):
    user_id: UUID
    channel: NotificationChannel = NotificationChannel.in_app
    title: str = Field(min_length=1)
    body: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class NotificationSendResponse(BaseModel):
    notification_id: str
    delivered: bool
    usage: UsageInfo


class NotificationProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError

    @abstractmethod
    def send(self, request: NotificationSendRequest) -> NotificationSendResponse:
        raise NotImplementedError


class MockNotificationProvider(NotificationProvider):
    def __init__(
        self,
        *,
        fail_with: Exception | None = None,
        simulate_timeout: bool = False,
        latency_ms: float = 1.0,
    ) -> None:
        self.sent: list[NotificationSendRequest] = []
        self._behavior = MockBehavior(
            fail_with=fail_with,
            simulate_timeout=simulate_timeout,
            latency_ms=latency_ms,
            provider_name="mock-notification",
        )
        self._meta = ProviderMetadata(
            name="mock-notification",
            vendor="mock",
            capabilities=frozenset({"notify"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def send(self, request: NotificationSendRequest) -> NotificationSendResponse:
        self._behavior.before_call(operation="send", timeout_seconds=request.timeout_seconds)
        self.sent.append(request)
        return NotificationSendResponse(
            notification_id=f"mock-notif-{len(self.sent)}",
            delivered=True,
            usage=self._behavior.usage(operation="send", unit_type="notifications", units=1.0),
        )
