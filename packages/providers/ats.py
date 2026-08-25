"""ATSAdapter — apply via known ATS job-board patterns using BrowserProvider.

Must never bypass CAPTCHA, auth walls, or anti-bot controls.
Submit only when explicitly permitted. SUBMITTED evidence is returned, never assumed.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl

from packages.providers.base import ProviderMetadata, TimeoutMixin
from packages.providers.browser import BrowserProvider


class ATSPauseReason(StrEnum):
    captcha = "captcha"
    unknown_question = "unknown_question"
    authentication_required = "authentication_required"
    unsupported_form = "unsupported_form"
    ambiguous = "ambiguous"
    anti_bot = "anti_bot"
    high_risk = "high_risk"
    submit_not_permitted = "submit_not_permitted"


class ATSDetectResult(BaseModel):
    matched: bool
    ats_name: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
    board_slug: str | None = None
    job_id: str | None = None


class ATSCandidateProfile(BaseModel):
    """Known candidate facts only — never invent missing fields."""

    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    location: str | None = None
    resume_path: str | None = None
    cover_letter_text: str | None = None
    answers: dict[str, str] = Field(default_factory=dict)


class ATSPrepareRequest(TimeoutMixin):
    application_url: HttpUrl | str
    session_id: str | None = None
    candidate: ATSCandidateProfile = Field(default_factory=ATSCandidateProfile)


class ATSPrepareResult(BaseModel):
    session_id: str
    ok: bool
    current_url: str | None = None
    known_fields: list[str] = Field(default_factory=list)
    unknown_questions: list[str] = Field(default_factory=list)
    requires_human: bool = False
    human_reason: ATSPauseReason | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class ATSFillRequest(TimeoutMixin):
    session_id: str
    fields: dict[str, str] = Field(default_factory=dict)


class ATSFillResult(BaseModel):
    ok: bool
    filled: list[str] = Field(default_factory=list)
    skipped_missing: list[str] = Field(default_factory=list)
    requires_human: bool = False
    human_reason: ATSPauseReason | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class ATSUploadRequest(TimeoutMixin):
    session_id: str
    resume_path: str
    selector: str | None = None


class ATSUploadResult(BaseModel):
    ok: bool
    uploaded_path: str | None = None
    requires_human: bool = False
    human_reason: ATSPauseReason | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class ATSAnswerRequest(TimeoutMixin):
    session_id: str
    answers: dict[str, str] = Field(default_factory=dict)


class ATSAnswerResult(BaseModel):
    ok: bool
    answered: list[str] = Field(default_factory=list)
    unknown_questions: list[str] = Field(default_factory=list)
    requires_human: bool = False
    human_reason: ATSPauseReason | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class ATSSubmitRequest(TimeoutMixin):
    session_id: str
    permitted: bool = False


class ATSSubmitResult(BaseModel):
    ok: bool
    submitted: bool = False
    requires_human: bool = False
    human_reason: ATSPauseReason | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class ATSVerifyRequest(TimeoutMixin):
    session_id: str
    expected_markers: list[str] = Field(default_factory=list)


class ATSVerifyResult(BaseModel):
    verified: bool
    confirmation_id: str | None = None
    confirmation_url: str | None = None
    screenshot_path: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class ATSAdapter(ABC):
    """One concrete ATS pattern per adapter — not a generic 'all ATS' shim."""

    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError

    @property
    @abstractmethod
    def ats_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def detect(self, *, url: str, html: str | None = None) -> ATSDetectResult:
        raise NotImplementedError

    @abstractmethod
    def prepare(self, browser: BrowserProvider, request: ATSPrepareRequest) -> ATSPrepareResult:
        raise NotImplementedError

    @abstractmethod
    def fill(self, browser: BrowserProvider, request: ATSFillRequest) -> ATSFillResult:
        raise NotImplementedError

    @abstractmethod
    def upload_resume(
        self, browser: BrowserProvider, request: ATSUploadRequest
    ) -> ATSUploadResult:
        raise NotImplementedError

    @abstractmethod
    def answer_questions(
        self, browser: BrowserProvider, request: ATSAnswerRequest
    ) -> ATSAnswerResult:
        raise NotImplementedError

    @abstractmethod
    def submit(self, browser: BrowserProvider, request: ATSSubmitRequest) -> ATSSubmitResult:
        raise NotImplementedError

    @abstractmethod
    def verify_submission(
        self, browser: BrowserProvider, request: ATSVerifyRequest
    ) -> ATSVerifyResult:
        raise NotImplementedError
