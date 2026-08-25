"""STEP 23 — ATSAdapter + Greenhouse adapter unit tests (mocked BrowserProvider)."""

from __future__ import annotations

from packages.providers.ats import ATSPauseReason
from packages.providers.browser import MockBrowserProvider
from packages.providers.greenhouse_ats import GreenhouseATSAdapter

GH_URL = "https://boards.greenhouse.io/acme/jobs/1234567"

GH_FORM_HTML = """
<html><body>
<form id="application_form">
  <input id="first_name" name="first_name" />
  <input id="last_name" name="last_name" />
  <input id="email" name="email" />
  <input id="phone" name="phone" />
  <input type="file" name="resume" />
  <button id="submit_app">Submit</button>
</form>
</body></html>
"""

GH_CAPTCHA_HTML = """
<html><body>
<form id="application_form">
  <div class="g-recaptcha"></div>
  <button id="submit_app">Submit</button>
</form>
</body></html>
"""

GH_UNKNOWN_HTML = """
<html><body>
<form id="application_form">
  <input id="first_name" />
  <div data-unknown-question="salary_expectation"></div>
  <button id="submit_app">Submit</button>
</form>
</body></html>
"""

GH_THANKS_HTML = """
<html><body>
<h1>Thank you for applying</h1>
<p>We have received your application.</p>
</body></html>
"""


def _adapter_with_html(html: str, url: str = GH_URL) -> tuple[GreenhouseATSAdapter, MockBrowserProvider, str]:
    adapter = GreenhouseATSAdapter()
    browser = MockBrowserProvider()
    session = browser.create_session()
    browser.seed_html(session.session_id, html, url=url)
    return adapter, browser, session.session_id


def test_detect_greenhouse_url() -> None:
    adapter = GreenhouseATSAdapter()
    result = adapter.detect(url=GH_URL)
    assert result.matched is True
    assert result.ats_name == "greenhouse"
    assert result.board_slug == "acme"
    assert result.job_id == "1234567"
    assert result.confidence >= 0.5


def test_detect_rejects_non_greenhouse() -> None:
    adapter = GreenhouseATSAdapter()
    result = adapter.detect(url="https://jobs.lever.co/acme/abc")
    assert result.matched is False
    assert result.ats_name is None


def test_prepare_lists_known_fields() -> None:
    adapter, browser, sid = _adapter_with_html(GH_FORM_HTML)
    from packages.providers.ats import ATSPrepareRequest

    result = adapter.prepare(
        browser,
        ATSPrepareRequest(application_url=GH_URL, session_id=sid),
    )
    assert result.ok is True
    assert "first_name" in result.known_fields
    assert "email" in result.known_fields
    assert result.requires_human is False


def test_prepare_pauses_on_captcha() -> None:
    adapter, browser, sid = _adapter_with_html(GH_CAPTCHA_HTML)
    from packages.providers.ats import ATSPrepareRequest

    result = adapter.prepare(
        browser,
        ATSPrepareRequest(application_url=GH_URL, session_id=sid),
    )
    assert result.requires_human is True
    assert result.human_reason == ATSPauseReason.captcha


def test_prepare_pauses_on_unknown_question() -> None:
    adapter, browser, sid = _adapter_with_html(GH_UNKNOWN_HTML)
    from packages.providers.ats import ATSPrepareRequest

    result = adapter.prepare(
        browser,
        ATSPrepareRequest(application_url=GH_URL, session_id=sid),
    )
    assert result.requires_human is True
    assert result.human_reason == ATSPauseReason.unknown_question
    assert "salary_expectation" in result.unknown_questions


def test_fill_and_upload() -> None:
    adapter, browser, sid = _adapter_with_html(GH_FORM_HTML)
    from packages.providers.ats import ATSFillRequest, ATSUploadRequest

    fill = adapter.fill(
        browser,
        ATSFillRequest(
            session_id=sid,
            fields={"first_name": "Ada", "last_name": "Lovelace", "email": "ada@example.com"},
        ),
    )
    assert fill.ok is True
    assert set(fill.filled) >= {"first_name", "last_name", "email"}

    upload = adapter.upload_resume(
        browser,
        ATSUploadRequest(session_id=sid, resume_path="/tmp/resume.pdf"),
    )
    assert upload.ok is True
    assert upload.uploaded_path == "/tmp/resume.pdf"


def test_submit_requires_permission() -> None:
    adapter, browser, sid = _adapter_with_html(GH_FORM_HTML)
    from packages.providers.ats import ATSSubmitRequest

    denied = adapter.submit(browser, ATSSubmitRequest(session_id=sid, permitted=False))
    assert denied.submitted is False
    assert denied.human_reason == ATSPauseReason.submit_not_permitted

    allowed = adapter.submit(browser, ATSSubmitRequest(session_id=sid, permitted=True))
    assert allowed.submitted is True
    assert allowed.evidence.get("clicked_submit") is True
    assert allowed.evidence.get("screenshot_path")


def test_verify_submission_needs_confirmation_markers() -> None:
    adapter, browser, sid = _adapter_with_html(GH_THANKS_HTML)
    from packages.providers.ats import ATSVerifyRequest

    # Seed confirmation page after "submit".
    browser.seed_html(sid, GH_THANKS_HTML, url=GH_URL + "/confirmation")
    result = adapter.verify_submission(browser, ATSVerifyRequest(session_id=sid))
    assert result.verified is True
    assert result.confirmation_id
    assert result.evidence.get("success") is True
    assert result.evidence.get("screenshot_path")


def test_submit_pauses_when_captcha_present() -> None:
    adapter, browser, sid = _adapter_with_html(GH_CAPTCHA_HTML)
    from packages.providers.ats import ATSSubmitRequest

    result = adapter.submit(browser, ATSSubmitRequest(session_id=sid, permitted=True))
    assert result.submitted is False
    assert result.human_reason == ATSPauseReason.captcha
