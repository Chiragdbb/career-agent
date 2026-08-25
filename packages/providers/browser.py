"""BrowserProvider — controlled browser automation.

Must never bypass CAPTCHA, auth walls, or anti-bot controls.
No stealth plugins. No credential harvesting. No ATS-specific logic.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl

from packages.providers.base import (
    MockBehavior,
    ProviderMetadata,
    TimeoutMixin,
    UsageInfo,
)
from packages.providers.exceptions import ProviderValidationError


class BrowserActionType(StrEnum):
    navigate = "navigate"
    click = "click"
    fill = "fill"
    select = "select"
    upload = "upload"
    screenshot = "screenshot"
    content = "content"  # HTML
    url = "url"
    shutdown = "shutdown"


class BrowserSession(BaseModel):
    session_id: str
    context_id: str
    url: HttpUrl | str | None = None
    title: str | None = None
    closed: bool = False


class BrowserAction(BaseModel):
    action: BrowserActionType
    selector: str | None = None
    value: str | None = None
    url: HttpUrl | str | None = None
    file_path: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: float = Field(default=30.0, gt=0)


class BrowserNavigateRequest(TimeoutMixin):
    url: HttpUrl | str
    wait_until: str = "domcontentloaded"
    session_id: str | None = None


class BrowserActionRequest(TimeoutMixin):
    session_id: str
    action: str  # click | type | fill | select | upload | extract | screenshot | content | url | shutdown
    selector: str | None = None
    value: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class BrowserSessionResponse(BaseModel):
    session_id: str
    url: HttpUrl | str
    title: str | None = None
    context_id: str | None = None
    usage: UsageInfo


class BrowserActionResponse(BaseModel):
    session_id: str
    ok: bool
    extracted_text: str | None = None
    screenshot_path: str | None = None
    html: str | None = None
    current_url: HttpUrl | str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    usage: UsageInfo
    requires_human: bool = False
    human_reason: str | None = None


class BrowserProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError

    @abstractmethod
    def create_session(self, *, timeout_seconds: float = 30.0) -> BrowserSession:
        """Create an isolated browser context/session."""

    @abstractmethod
    def navigate(self, request: BrowserNavigateRequest) -> BrowserSessionResponse:
        raise NotImplementedError

    @abstractmethod
    def action(self, request: BrowserActionRequest) -> BrowserActionResponse:
        raise NotImplementedError

    @abstractmethod
    def run_action(self, session_id: str, action: BrowserAction) -> BrowserActionResponse:
        """Typed action helper (nav/click/fill/select/upload/screenshot/html/url/shutdown)."""

    @abstractmethod
    def shutdown(self, session_id: str | None = None) -> None:
        """Close one session or all sessions."""


class MockBrowserProvider(BrowserProvider):
    def __init__(
        self,
        *,
        fail_with: Exception | None = None,
        simulate_timeout: bool = False,
        latency_ms: float = 15.0,
        detect_captcha_text: bool = True,
    ) -> None:
        self._sessions: dict[str, BrowserSession] = {}
        self._pages: dict[str, dict[str, Any]] = {}
        self._detect_captcha = detect_captcha_text
        self._behavior = MockBehavior(
            fail_with=fail_with,
            simulate_timeout=simulate_timeout,
            latency_ms=latency_ms,
            provider_name="mock-browser",
        )
        self._meta = ProviderMetadata(
            name="mock-browser",
            vendor="mock",
            capabilities=frozenset(
                {
                    "create_session",
                    "navigate",
                    "click",
                    "fill",
                    "select",
                    "upload",
                    "screenshot",
                    "content",
                    "url",
                    "shutdown",
                }
            ),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def seed_html(self, session_id: str, html: str, *, url: str | None = None) -> None:
        """Test helper: set page HTML for an existing session."""
        if session_id not in self._sessions:
            raise ProviderValidationError(
                "unknown session",
                provider="mock-browser",
                operation="seed_html",
            )
        page = self._pages.setdefault(
            session_id, {"url": "about:blank", "title": "", "html": "", "fields": {}}
        )
        page["html"] = html
        if url is not None:
            page["url"] = url
            self._sessions[session_id].url = url

    def create_session(self, *, timeout_seconds: float = 30.0) -> BrowserSession:
        self._behavior.before_call(operation="create_session", timeout_seconds=timeout_seconds)
        session_id = f"mock-session-{uuid.uuid4().hex[:8]}"
        context_id = f"mock-context-{uuid.uuid4().hex[:8]}"
        session = BrowserSession(session_id=session_id, context_id=context_id, url=None)
        self._sessions[session_id] = session
        self._pages[session_id] = {"url": "about:blank", "title": "", "html": "<html></html>", "fields": {}}
        return session

    def navigate(self, request: BrowserNavigateRequest) -> BrowserSessionResponse:
        self._behavior.before_call(operation="navigate", timeout_seconds=request.timeout_seconds)
        session_id = request.session_id
        if not session_id or session_id not in self._sessions:
            created = self.create_session(timeout_seconds=request.timeout_seconds)
            session_id = created.session_id
        session = self._sessions[session_id]
        if session.closed:
            raise ProviderValidationError(
                "session is closed",
                provider="mock-browser",
                operation="navigate",
            )
        url = str(request.url)
        session.url = url
        session.title = "Mock Browser Page"
        # Preserve seeded HTML for ATS fixtures when URL matches a Greenhouse board.
        existing = self._pages.get(session_id, {})
        seeded = existing.get("html") or ""
        if "application_form" in seeded or "greenhouse" in seeded.lower():
            html = seeded
        else:
            html = f"<html><body><h1>Mock</h1><a href='{url}'>link</a></body></html>"
        self._pages[session_id] = {
            "url": url,
            "title": session.title,
            "html": html,
            "fields": existing.get("fields") or {},
        }
        return BrowserSessionResponse(
            session_id=session_id,
            url=url,
            title=session.title,
            context_id=session.context_id,
            usage=self._behavior.usage(operation="navigate", unit_type="sessions", units=1.0),
        )

    def action(self, request: BrowserActionRequest) -> BrowserActionResponse:
        self._behavior.before_call(operation="action", timeout_seconds=request.timeout_seconds)
        mapped = request.action
        if mapped == "type":
            mapped = BrowserActionType.fill.value
        if mapped == "extract":
            mapped = BrowserActionType.content.value
        return self.run_action(
            request.session_id,
            BrowserAction(
                action=BrowserActionType(mapped),
                selector=request.selector,
                value=request.value,
                params=request.params,
                timeout_seconds=request.timeout_seconds,
            ),
        )

    def run_action(self, session_id: str, action: BrowserAction) -> BrowserActionResponse:
        self._behavior.before_call(
            operation=action.action.value,
            timeout_seconds=action.timeout_seconds,
        )
        session = self._sessions.get(session_id)
        if session is None or session.closed:
            raise ProviderValidationError(
                "unknown or closed session",
                provider="mock-browser",
                operation=action.action.value,
            )
        page = self._pages[session_id]

        if action.action == BrowserActionType.shutdown:
            self.shutdown(session_id)
            return BrowserActionResponse(
                session_id=session_id,
                ok=True,
                data={"closed": True},
                usage=self._behavior.usage(operation="shutdown", unit_type="actions", units=1.0),
            )

        if action.action == BrowserActionType.navigate:
            if not action.url:
                raise ProviderValidationError(
                    "navigate requires url",
                    provider="mock-browser",
                    operation="navigate",
                )
            nav = self.navigate(
                BrowserNavigateRequest(
                    url=action.url,
                    session_id=session_id,
                    timeout_seconds=action.timeout_seconds,
                )
            )
            return BrowserActionResponse(
                session_id=session_id,
                ok=True,
                current_url=nav.url,
                usage=nav.usage,
            )

        if action.action == BrowserActionType.click:
            return BrowserActionResponse(
                session_id=session_id,
                ok=True,
                data={"clicked": action.selector},
                current_url=page["url"],
                usage=self._behavior.usage(operation="click", unit_type="actions", units=1.0),
            )

        if action.action in (BrowserActionType.fill, BrowserActionType.select):
            if action.selector:
                page["fields"][action.selector] = action.value
            return BrowserActionResponse(
                session_id=session_id,
                ok=True,
                data={"selector": action.selector, "value": action.value},
                usage=self._behavior.usage(
                    operation=action.action.value, unit_type="actions", units=1.0
                ),
            )

        if action.action == BrowserActionType.upload:
            return BrowserActionResponse(
                session_id=session_id,
                ok=True,
                data={"uploaded": action.file_path or action.value},
                usage=self._behavior.usage(operation="upload", unit_type="actions", units=1.0),
            )

        if action.action == BrowserActionType.screenshot:
            path = f"/tmp/mock-screenshot-{session_id}.png"
            return BrowserActionResponse(
                session_id=session_id,
                ok=True,
                screenshot_path=path,
                usage=self._behavior.usage(operation="screenshot", unit_type="actions", units=1.0),
            )

        if action.action == BrowserActionType.content:
            html = page.get("html") or ""
            requires_human = False
            reason = None
            if self._detect_captcha and "captcha" in html.lower():
                requires_human = True
                reason = "captcha_detected"
            return BrowserActionResponse(
                session_id=session_id,
                ok=True,
                extracted_text="mock extracted text",
                html=html,
                current_url=page["url"],
                requires_human=requires_human,
                human_reason=reason,
                usage=self._behavior.usage(operation="content", unit_type="actions", units=1.0),
            )

        if action.action == BrowserActionType.url:
            return BrowserActionResponse(
                session_id=session_id,
                ok=True,
                current_url=page["url"],
                usage=self._behavior.usage(operation="url", unit_type="actions", units=1.0),
            )

        raise ProviderValidationError(
            f"unsupported action: {action.action}",
            provider="mock-browser",
            operation=str(action.action),
        )

    def shutdown(self, session_id: str | None = None) -> None:
        if session_id is None:
            for sid in list(self._sessions):
                self.shutdown(sid)
            return
        session = self._sessions.get(session_id)
        if session is not None:
            session.closed = True
            self._pages.pop(session_id, None)
