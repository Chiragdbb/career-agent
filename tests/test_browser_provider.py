"""STEP 21 — BrowserProvider (mock for CI; Playwright optional)."""

from __future__ import annotations

import pytest

from packages.providers.browser import (
    BrowserAction,
    BrowserActionRequest,
    BrowserActionType,
    BrowserNavigateRequest,
    MockBrowserProvider,
)
from packages.providers.exceptions import ProviderNotConfiguredError, ProviderValidationError
from packages.providers.playwright_browser import PlaywrightBrowserProvider


def test_mock_session_actions_and_shutdown() -> None:
    browser = MockBrowserProvider()
    session = browser.create_session()
    assert session.context_id

    nav = browser.navigate(
        BrowserNavigateRequest(url="https://example.com/apply", session_id=session.session_id)
    )
    assert "example.com" in str(nav.url)

    click = browser.run_action(
        session.session_id,
        BrowserAction(action=BrowserActionType.click, selector="#submit"),
    )
    assert click.ok

    fill = browser.run_action(
        session.session_id,
        BrowserAction(action=BrowserActionType.fill, selector="#name", value="Pat"),
    )
    assert fill.data["value"] == "Pat"

    select = browser.run_action(
        session.session_id,
        BrowserAction(action=BrowserActionType.select, selector="#country", value="US"),
    )
    assert select.ok

    upload = browser.run_action(
        session.session_id,
        BrowserAction(action=BrowserActionType.upload, selector="#resume", file_path="/tmp/r.pdf"),
    )
    assert upload.ok

    shot = browser.run_action(
        session.session_id,
        BrowserAction(action=BrowserActionType.screenshot),
    )
    assert shot.screenshot_path

    html = browser.run_action(
        session.session_id,
        BrowserAction(action=BrowserActionType.content),
    )
    assert html.html

    url = browser.run_action(
        session.session_id,
        BrowserAction(action=BrowserActionType.url),
    )
    assert "example.com" in str(url.current_url)

    # Legacy action() API still works
    legacy = browser.action(
        BrowserActionRequest(session_id=session.session_id, action="extract", selector="body")
    )
    assert legacy.extracted_text

    browser.shutdown(session.session_id)
    with pytest.raises(ProviderValidationError):
        browser.run_action(
            session.session_id,
            BrowserAction(action=BrowserActionType.click, selector="#x"),
        )


def test_playwright_requires_install_or_runs() -> None:
    try:
        provider = PlaywrightBrowserProvider(headless=True)
    except ProviderNotConfiguredError:
        return
    # If Playwright is installed, create/shutdown should work without navigating the open web.
    session = provider.create_session()
    provider.shutdown(session.session_id)
    provider.shutdown()
