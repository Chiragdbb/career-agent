"""Greenhouse job-board ATS adapter (boards.greenhouse.io pattern).

Targets public Greenhouse application forms — not a generic multi-ATS shim.
Uses BrowserProvider only. Never bypasses CAPTCHA / auth / anti-bot.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from packages.providers.ats import (
    ATSAdapter,
    ATSAnswerRequest,
    ATSAnswerResult,
    ATSCandidateProfile,
    ATSDetectResult,
    ATSFillRequest,
    ATSFillResult,
    ATSPauseReason,
    ATSPrepareRequest,
    ATSPrepareResult,
    ATSSubmitRequest,
    ATSSubmitResult,
    ATSUploadRequest,
    ATSUploadResult,
    ATSVerifyRequest,
    ATSVerifyResult,
)
from packages.providers.base import ProviderMetadata
from packages.providers.browser import (
    BrowserAction,
    BrowserActionType,
    BrowserNavigateRequest,
    BrowserProvider,
)

# Public Greenhouse board URL patterns.
_GH_HOSTS = (
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "boards-api.greenhouse.io",
)
_BOARD_JOB_RE = re.compile(
    r"https?://(?:job-)?boards\.greenhouse\.io/([^/]+)/jobs/(\d+)",
    re.IGNORECASE,
)

# Well-documented Greenhouse application field name attributes / ids.
KNOWN_FIELD_SELECTORS: dict[str, str] = {
    "first_name": "#first_name",
    "last_name": "#last_name",
    "email": "#email",
    "phone": "#phone",
    "linkedin": 'input[name="job_application[linkedin_profile_url]"]',
    "location": 'input[name="job_application[location]"]',
    "cover_letter": "#cover_letter_text",
}

RESUME_SELECTOR = 'input[type="file"][name="resume"]'
SUBMIT_SELECTOR = "#submit_app"
FORM_MARKER = "#application_form"
CAPTCHA_MARKERS = ("g-recaptcha", "h-captcha", "cf-turnstile", "captcha")
LOGIN_MARKERS = ("sign in", "log in", "sso", "authentication required")
CONFIRMATION_MARKERS = (
    "thank you for applying",
    "application submitted",
    "we have received your application",
    "thanks for applying",
)


class GreenhouseATSAdapter(ATSAdapter):
    """Adapter for Greenhouse-hosted job board application forms."""

    def __init__(self) -> None:
        self._meta = ProviderMetadata(
            name="greenhouse-ats",
            vendor="greenhouse",
            capabilities=frozenset(
                {
                    "detect",
                    "prepare",
                    "fill",
                    "upload_resume",
                    "answer_questions",
                    "submit",
                    "verify_submission",
                }
            ),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    @property
    def ats_name(self) -> str:
        return "greenhouse"

    def detect(self, *, url: str, html: str | None = None) -> ATSDetectResult:
        reasons: list[str] = []
        board_slug: str | None = None
        job_id: str | None = None
        confidence = 0.0

        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if any(host == h or host.endswith("." + h) for h in _GH_HOSTS):
            confidence += 0.5
            reasons.append(f"host matches Greenhouse board pattern: {host}")

        match = _BOARD_JOB_RE.search(url)
        if match:
            board_slug, job_id = match.group(1), match.group(2)
            confidence += 0.3
            reasons.append(f"board job URL slug={board_slug} job_id={job_id}")

        if html:
            lower = html.lower()
            if FORM_MARKER.lstrip("#") in lower or 'id="application_form"' in lower:
                confidence += 0.15
                reasons.append("application_form marker present")
            if "greenhouse" in lower:
                confidence += 0.05
                reasons.append("greenhouse string in HTML")

        confidence = min(confidence, 1.0)
        matched = confidence >= 0.5
        return ATSDetectResult(
            matched=matched,
            ats_name=self.ats_name if matched else None,
            confidence=confidence,
            reasons=reasons,
            board_slug=board_slug,
            job_id=job_id,
        )

    def prepare(
        self, browser: BrowserProvider, request: ATSPrepareRequest
    ) -> ATSPrepareResult:
        url = str(request.application_url)
        detection = self.detect(url=url)
        if not detection.matched:
            return ATSPrepareResult(
                session_id=request.session_id or "",
                ok=False,
                requires_human=True,
                human_reason=ATSPauseReason.unsupported_form,
                evidence={"detect": detection.model_dump()},
            )

        session_id = request.session_id
        if not session_id:
            session = browser.create_session(timeout_seconds=request.timeout_seconds)
            session_id = session.session_id

        nav = browser.navigate(
            BrowserNavigateRequest(
                url=url,
                session_id=session_id,
                timeout_seconds=request.timeout_seconds,
            )
        )
        session_id = nav.session_id
        content = browser.run_action(
            session_id,
            BrowserAction(
                action=BrowserActionType.content,
                timeout_seconds=request.timeout_seconds,
            ),
        )
        html = content.html or ""
        lower = html.lower()

        if content.requires_human or any(m in lower for m in CAPTCHA_MARKERS):
            return ATSPrepareResult(
                session_id=session_id,
                ok=False,
                current_url=str(nav.url),
                requires_human=True,
                human_reason=ATSPauseReason.captcha,
                evidence={"html_snippet": html[:500], "screenshot": content.screenshot_path},
            )

        if any(m in lower for m in LOGIN_MARKERS) and FORM_MARKER.lstrip("#") not in lower:
            return ATSPrepareResult(
                session_id=session_id,
                ok=False,
                current_url=str(nav.url),
                requires_human=True,
                human_reason=ATSPauseReason.authentication_required,
                evidence={"html_snippet": html[:500]},
            )

        # Greenhouse board apps use a documented core field set.
        known = list(KNOWN_FIELD_SELECTORS.keys())
        form_present = "application_form" in lower or 'id="application_form"' in lower

        unknown = self._extract_unknown_questions(html)
        requires_human = bool(unknown)
        human_reason = ATSPauseReason.unknown_question if unknown else None

        return ATSPrepareResult(
            session_id=session_id,
            ok=not requires_human,
            current_url=str(nav.url),
            known_fields=known,
            unknown_questions=unknown,
            requires_human=requires_human,
            human_reason=human_reason,
            evidence={
                "detect": detection.model_dump(),
                "form_present": form_present,
            },
        )

    def fill(self, browser: BrowserProvider, request: ATSFillRequest) -> ATSFillResult:
        filled: list[str] = []
        skipped: list[str] = []
        for key, value in request.fields.items():
            selector = KNOWN_FIELD_SELECTORS.get(key)
            if not selector:
                skipped.append(key)
                continue
            if value is None or not str(value).strip():
                skipped.append(key)
                continue
            resp = browser.run_action(
                request.session_id,
                BrowserAction(
                    action=BrowserActionType.fill,
                    selector=selector,
                    value=str(value),
                    timeout_seconds=request.timeout_seconds,
                ),
            )
            if resp.requires_human:
                return ATSFillResult(
                    ok=False,
                    filled=filled,
                    skipped_missing=skipped,
                    requires_human=True,
                    human_reason=ATSPauseReason.high_risk,
                    evidence={"browser_reason": resp.human_reason},
                )
            filled.append(key)

        return ATSFillResult(
            ok=True,
            filled=filled,
            skipped_missing=skipped,
            evidence={"filled_count": len(filled)},
        )

    def upload_resume(
        self, browser: BrowserProvider, request: ATSUploadRequest
    ) -> ATSUploadResult:
        if not request.resume_path or not request.resume_path.strip():
            return ATSUploadResult(
                ok=False,
                requires_human=True,
                human_reason=ATSPauseReason.ambiguous,
                evidence={"error": "resume_path required"},
            )
        selector = request.selector or RESUME_SELECTOR
        resp = browser.run_action(
            request.session_id,
            BrowserAction(
                action=BrowserActionType.upload,
                selector=selector,
                file_path=request.resume_path,
                value=request.resume_path,
                timeout_seconds=request.timeout_seconds,
            ),
        )
        if resp.requires_human:
            return ATSUploadResult(
                ok=False,
                requires_human=True,
                human_reason=ATSPauseReason.high_risk,
                evidence={"browser_reason": resp.human_reason},
            )
        return ATSUploadResult(
            ok=True,
            uploaded_path=request.resume_path,
            evidence={"selector": selector},
        )

    def answer_questions(
        self, browser: BrowserProvider, request: ATSAnswerRequest
    ) -> ATSAnswerResult:
        answered: list[str] = []
        unknown: list[str] = []
        for question_key, answer in request.answers.items():
            if not answer or not str(answer).strip():
                unknown.append(question_key)
                continue
            # Greenhouse custom questions often use data-question or name attributes.
            selector = (
                f'textarea[name="{question_key}"], '
                f'input[name="{question_key}"], '
                f'#{question_key}'
            )
            resp = browser.run_action(
                request.session_id,
                BrowserAction(
                    action=BrowserActionType.fill,
                    selector=selector,
                    value=str(answer),
                    timeout_seconds=request.timeout_seconds,
                ),
            )
            if resp.requires_human:
                return ATSAnswerResult(
                    ok=False,
                    answered=answered,
                    unknown_questions=unknown + [question_key],
                    requires_human=True,
                    human_reason=ATSPauseReason.unknown_question,
                    evidence={"browser_reason": resp.human_reason},
                )
            answered.append(question_key)

        requires_human = bool(unknown)
        return ATSAnswerResult(
            ok=not requires_human,
            answered=answered,
            unknown_questions=unknown,
            requires_human=requires_human,
            human_reason=ATSPauseReason.unknown_question if requires_human else None,
            evidence={},
        )

    def submit(
        self, browser: BrowserProvider, request: ATSSubmitRequest
    ) -> ATSSubmitResult:
        if not request.permitted:
            return ATSSubmitResult(
                ok=False,
                submitted=False,
                requires_human=True,
                human_reason=ATSPauseReason.submit_not_permitted,
                evidence={"message": "submit requires explicit permission"},
            )

        # Re-check page for CAPTCHA / anti-bot before clicking submit.
        content = browser.run_action(
            request.session_id,
            BrowserAction(
                action=BrowserActionType.content,
                timeout_seconds=request.timeout_seconds,
            ),
        )
        html = (content.html or "").lower()
        if content.requires_human or any(m in html for m in CAPTCHA_MARKERS):
            return ATSSubmitResult(
                ok=False,
                submitted=False,
                requires_human=True,
                human_reason=ATSPauseReason.captcha,
                evidence={"html_snippet": html[:500]},
            )

        click = browser.run_action(
            request.session_id,
            BrowserAction(
                action=BrowserActionType.click,
                selector=SUBMIT_SELECTOR,
                timeout_seconds=request.timeout_seconds,
            ),
        )
        if not click.ok or click.requires_human:
            return ATSSubmitResult(
                ok=False,
                submitted=False,
                requires_human=True,
                human_reason=ATSPauseReason.high_risk,
                evidence={"browser_reason": click.human_reason},
            )

        screenshot = browser.run_action(
            request.session_id,
            BrowserAction(
                action=BrowserActionType.screenshot,
                timeout_seconds=request.timeout_seconds,
            ),
        )
        url_resp = browser.run_action(
            request.session_id,
            BrowserAction(
                action=BrowserActionType.url,
                timeout_seconds=request.timeout_seconds,
            ),
        )
        evidence: dict[str, Any] = {
            "clicked_submit": True,
            "screenshot_path": screenshot.screenshot_path,
            "current_url": str(url_resp.current_url) if url_resp.current_url else None,
            "ats": self.ats_name,
        }
        return ATSSubmitResult(
            ok=True,
            submitted=True,
            evidence=evidence,
        )

    def verify_submission(
        self, browser: BrowserProvider, request: ATSVerifyRequest
    ) -> ATSVerifyResult:
        content = browser.run_action(
            request.session_id,
            BrowserAction(
                action=BrowserActionType.content,
                timeout_seconds=request.timeout_seconds,
            ),
        )
        html = (content.html or "").lower()
        text = (content.extracted_text or "").lower()
        combined = f"{html}\n{text}"
        markers = request.expected_markers or list(CONFIRMATION_MARKERS)
        matched = [m for m in markers if m.lower() in combined]

        screenshot = browser.run_action(
            request.session_id,
            BrowserAction(
                action=BrowserActionType.screenshot,
                timeout_seconds=request.timeout_seconds,
            ),
        )
        url_resp = browser.run_action(
            request.session_id,
            BrowserAction(
                action=BrowserActionType.url,
                timeout_seconds=request.timeout_seconds,
            ),
        )
        confirmation_url = str(url_resp.current_url) if url_resp.current_url else None
        verified = bool(matched)
        confirmation_id = None
        if verified and confirmation_url:
            # Greenhouse confirmation pages sometimes include /confirmation or thank_you.
            confirmation_id = f"gh-confirm:{confirmation_url}"

        return ATSVerifyResult(
            verified=verified,
            confirmation_id=confirmation_id if verified else None,
            confirmation_url=confirmation_url if verified else None,
            screenshot_path=screenshot.screenshot_path,
            evidence={
                "matched_markers": matched,
                "success": verified,
                "proof": matched[0] if matched else None,
                "screenshot_path": screenshot.screenshot_path,
                "confirmation_url": confirmation_url if verified else None,
                "confirmation_id": confirmation_id if verified else None,
            },
        )

    @staticmethod
    def fields_from_candidate(candidate: ATSCandidateProfile) -> dict[str, str]:
        mapping = {
            "first_name": candidate.first_name,
            "last_name": candidate.last_name,
            "email": candidate.email,
            "phone": candidate.phone,
            "linkedin": candidate.linkedin_url,
            "location": candidate.location,
            "cover_letter": candidate.cover_letter_text,
        }
        return {k: v for k, v in mapping.items() if v and str(v).strip()}

    @staticmethod
    def _extract_unknown_questions(html: str) -> list[str]:
        """Flag custom Greenhouse questions that lack mapped answers."""
        unknown: list[str] = []
        # data-question / required custom fields without known keys.
        for match in re.finditer(
            r'data-question(?:-id)?=["\']([^"\']+)["\']',
            html,
            re.IGNORECASE,
        ):
            qid = match.group(1)
            if qid not in KNOWN_FIELD_SELECTORS:
                unknown.append(qid)
        # Explicit unknown marker used in fixtures/tests.
        if "data-unknown-question" in html.lower():
            for match in re.finditer(
                r'data-unknown-question=["\']([^"\']+)["\']',
                html,
                re.IGNORECASE,
            ):
                unknown.append(match.group(1))
        return list(dict.fromkeys(unknown))
