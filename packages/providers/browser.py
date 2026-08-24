"""BrowserProvider — controlled browser automation (e.g. Playwright).

Must never bypass CAPTCHA, auth walls, or anti-bot controls.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field, HttpUrl

from packages.providers.base import (
    MockBehavior,
    ProviderMetadata,
    TimeoutMixin,
    UsageInfo,
)


class BrowserNavigateRequest(TimeoutMixin):
    url: HttpUrl | str
    wait_until: str = "domcontentloaded"


class BrowserActionRequest(TimeoutMixin):
    session_id: str
    action: str  # click | type | extract | screenshot | ...
    selector: str | None = None
    value: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class BrowserSessionResponse(BaseModel):
    session_id: str
    url: HttpUrl | str
    title: str | None = None
    usage: UsageInfo


class BrowserActionResponse(BaseModel):
    session_id: str
    ok: bool
    extracted_text: str | None = None
    screenshot_path: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    usage: UsageInfo


class BrowserProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError

    @abstractmethod
    def navigate(self, request: BrowserNavigateRequest) -> BrowserSessionResponse:
        raise NotImplementedError

    @abstractmethod
    def action(self, request: BrowserActionRequest) -> BrowserActionResponse:
        raise NotImplementedError


class MockBrowserProvider(BrowserProvider):
    def __init__(
        self,
        *,
        fail_with: Exception | None = None,
        simulate_timeout: bool = False,
        latency_ms: float = 15.0,
    ) -> None:
        self._sessions: dict[str, str] = {}
        self._behavior = MockBehavior(
            fail_with=fail_with,
            simulate_timeout=simulate_timeout,
            latency_ms=latency_ms,
            provider_name="mock-browser",
        )
        self._meta = ProviderMetadata(
            name="mock-browser",
            vendor="mock",
            capabilities=frozenset({"navigate", "action"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def navigate(self, request: BrowserNavigateRequest) -> BrowserSessionResponse:
        self._behavior.before_call(operation="navigate", timeout_seconds=request.timeout_seconds)
        session_id = f"mock-session-{len(self._sessions) + 1}"
        self._sessions[session_id] = str(request.url)
        return BrowserSessionResponse(
            session_id=session_id,
            url=request.url,
            title="Mock Browser Page",
            usage=self._behavior.usage(operation="navigate", unit_type="sessions", units=1.0),
        )

    def action(self, request: BrowserActionRequest) -> BrowserActionResponse:
        self._behavior.before_call(operation="action", timeout_seconds=request.timeout_seconds)
        return BrowserActionResponse(
            session_id=request.session_id,
            ok=True,
            extracted_text="mock extracted text" if request.action == "extract" else None,
            data={"action": request.action, "selector": request.selector},
            usage=self._behavior.usage(operation="action", unit_type="actions", units=1.0),
        )
