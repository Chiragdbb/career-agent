"""Optional Playwright BrowserProvider adapter.

Not required for CI — MockBrowserProvider covers tests.
Install: pip install playwright && playwright install chromium
"""

from __future__ import annotations

import uuid
from typing import Any

from packages.providers.base import ProviderMetadata, UsageInfo
from packages.providers.browser import (
    BrowserAction,
    BrowserActionRequest,
    BrowserActionResponse,
    BrowserActionType,
    BrowserNavigateRequest,
    BrowserProvider,
    BrowserSession,
    BrowserSessionResponse,
)
from packages.providers.exceptions import (
    ProviderNotConfiguredError,
    ProviderUnavailableError,
    ProviderValidationError,
)


class PlaywrightBrowserProvider(BrowserProvider):
    """Isolated Playwright contexts. No stealth, no captcha bypass, no credential harvest."""

    def __init__(self, *, headless: bool = True, default_timeout_ms: int = 30000) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise ProviderNotConfiguredError(
                "playwright is not installed; use MockBrowserProvider in CI",
                provider="playwright-browser",
            ) from exc
        self._sync_playwright = sync_playwright
        self._headless = headless
        self._default_timeout_ms = default_timeout_ms
        self._pw = None
        self._browser = None
        self._contexts: dict[str, Any] = {}
        self._pages: dict[str, Any] = {}
        self._sessions: dict[str, BrowserSession] = {}
        self._meta = ProviderMetadata(
            name="playwright-browser",
            vendor="playwright",
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

    def _ensure_browser(self) -> None:
        if self._browser is not None:
            return
        try:
            self._pw = self._sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=self._headless)
        except Exception as exc:
            raise ProviderUnavailableError(
                f"Failed to launch Playwright browser: {exc}",
                provider="playwright-browser",
                operation="launch",
            ) from exc

    def create_session(self, *, timeout_seconds: float = 30.0) -> BrowserSession:
        self._ensure_browser()
        assert self._browser is not None
        context = self._browser.new_context()
        page = context.new_page()
        page.set_default_timeout(int(timeout_seconds * 1000) or self._default_timeout_ms)
        session_id = f"pw-session-{uuid.uuid4().hex[:8]}"
        context_id = f"pw-context-{uuid.uuid4().hex[:8]}"
        session = BrowserSession(session_id=session_id, context_id=context_id)
        self._sessions[session_id] = session
        self._contexts[session_id] = context
        self._pages[session_id] = page
        return session

    def navigate(self, request: BrowserNavigateRequest) -> BrowserSessionResponse:
        session_id = request.session_id
        if not session_id or session_id not in self._sessions:
            created = self.create_session(timeout_seconds=request.timeout_seconds)
            session_id = created.session_id
        page = self._pages[session_id]
        page.goto(str(request.url), wait_until=request.wait_until)
        session = self._sessions[session_id]
        session.url = page.url
        session.title = page.title()
        return BrowserSessionResponse(
            session_id=session_id,
            url=page.url,
            title=session.title,
            context_id=session.context_id,
            usage=UsageInfo(
                operation="navigate",
                unit_type="sessions",
                units=1.0,
                provider="playwright-browser",
            ),
        )

    def action(self, request: BrowserActionRequest) -> BrowserActionResponse:
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
        if session_id not in self._sessions or self._sessions[session_id].closed:
            raise ProviderValidationError(
                "unknown or closed session",
                provider="playwright-browser",
                operation=action.action.value,
            )
        page = self._pages[session_id]

        if action.action == BrowserActionType.shutdown:
            self.shutdown(session_id)
            return BrowserActionResponse(
                session_id=session_id,
                ok=True,
                data={"closed": True},
                usage=UsageInfo(
                    operation="shutdown",
                    unit_type="actions",
                    units=1.0,
                    provider="playwright-browser",
                ),
            )

        if action.action == BrowserActionType.navigate:
            if not action.url:
                raise ProviderValidationError(
                    "navigate requires url",
                    provider="playwright-browser",
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
            if not action.selector:
                raise ProviderValidationError(
                    "click requires selector",
                    provider="playwright-browser",
                    operation="click",
                )
            page.click(action.selector, timeout=int(action.timeout_seconds * 1000))
        elif action.action == BrowserActionType.fill:
            if not action.selector:
                raise ProviderValidationError(
                    "fill requires selector",
                    provider="playwright-browser",
                    operation="fill",
                )
            page.fill(action.selector, action.value or "", timeout=int(action.timeout_seconds * 1000))
        elif action.action == BrowserActionType.select:
            if not action.selector:
                raise ProviderValidationError(
                    "select requires selector",
                    provider="playwright-browser",
                    operation="select",
                )
            page.select_option(action.selector, action.value or "")
        elif action.action == BrowserActionType.upload:
            if not action.selector:
                raise ProviderValidationError(
                    "upload requires selector",
                    provider="playwright-browser",
                    operation="upload",
                )
            path = action.file_path or action.value
            page.set_input_files(action.selector, path)
        elif action.action == BrowserActionType.screenshot:
            path = action.file_path or f"/tmp/pw-screenshot-{session_id}.png"
            page.screenshot(path=path)
            return BrowserActionResponse(
                session_id=session_id,
                ok=True,
                screenshot_path=path,
                current_url=page.url,
                usage=UsageInfo(
                    operation="screenshot",
                    unit_type="actions",
                    units=1.0,
                    provider="playwright-browser",
                ),
            )
        elif action.action == BrowserActionType.content:
            html = page.content()
            requires_human = "captcha" in html.lower()
            return BrowserActionResponse(
                session_id=session_id,
                ok=True,
                html=html,
                extracted_text=page.inner_text("body") if page.query_selector("body") else None,
                current_url=page.url,
                requires_human=requires_human,
                human_reason="captcha_detected" if requires_human else None,
                usage=UsageInfo(
                    operation="content",
                    unit_type="actions",
                    units=1.0,
                    provider="playwright-browser",
                ),
            )
        elif action.action == BrowserActionType.url:
            return BrowserActionResponse(
                session_id=session_id,
                ok=True,
                current_url=page.url,
                usage=UsageInfo(
                    operation="url",
                    unit_type="actions",
                    units=1.0,
                    provider="playwright-browser",
                ),
            )
        else:
            raise ProviderValidationError(
                f"unsupported action: {action.action}",
                provider="playwright-browser",
                operation=str(action.action),
            )

        return BrowserActionResponse(
            session_id=session_id,
            ok=True,
            current_url=page.url,
            data={"action": action.action.value, "selector": action.selector},
            usage=UsageInfo(
                operation=action.action.value,
                unit_type="actions",
                units=1.0,
                provider="playwright-browser",
            ),
        )

    def shutdown(self, session_id: str | None = None) -> None:
        if session_id is None:
            for sid in list(self._sessions):
                self.shutdown(sid)
            if self._browser is not None:
                self._browser.close()
                self._browser = None
            if self._pw is not None:
                self._pw.stop()
                self._pw = None
            return
        session = self._sessions.get(session_id)
        if session is None:
            return
        session.closed = True
        context = self._contexts.pop(session_id, None)
        self._pages.pop(session_id, None)
        if context is not None:
            context.close()
