"""EmailSenderProvider — outbound email delivery.

External communication must still require user approval at the service layer.
Default real target: Resend. Mock for CI when RESEND_API_KEY is unset.
Optional SMTP fallback for local/self-hosted; optional SES stub clearly marked.
"""

from __future__ import annotations

import smtplib
import uuid
from abc import ABC, abstractmethod
from email.message import EmailMessage
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from packages.providers.base import (
    MockBehavior,
    ProviderMetadata,
    TimeoutMixin,
    UsageInfo,
)
from packages.providers.exceptions import (
    ProviderNotConfiguredError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from packages.providers.http_utils import request_with_retries


class EmailDeliveryState(StrEnum):
    """Provider-level delivery states (domain maps these onto outreach events)."""

    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    QUEUED = "QUEUED"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    BOUNCED = "BOUNCED"
    FAILED = "FAILED"
    REPLIED = "REPLIED"


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
    delivery_state: EmailDeliveryState = EmailDeliveryState.SENT
    usage: UsageInfo
    raw: dict[str, Any] = Field(default_factory=dict)


class EmailSenderProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError

    @abstractmethod
    def send_email(self, request: EmailSendRequest) -> EmailSendResponse:
        """Deliver already-approved content. Does not decide approval."""


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
        if not request.to:
            raise ProviderValidationError(
                "to is required",
                provider="mock-email-sender",
                operation="send_email",
            )
        self.sent.append(request)
        return EmailSendResponse(
            message_id=f"mock-msg-{uuid.uuid4().hex[:12]}",
            accepted=list(request.to),
            delivery_state=EmailDeliveryState.SENT,
            usage=self._behavior.usage(
                operation="send_email", unit_type="emails", units=float(len(request.to))
            ),
        )


class ResendEmailSenderProvider(EmailSenderProvider):
    """Resend HTTP API adapter — default EmailSenderProvider target.

    Does not auto-send; callers (OutreachService) must only invoke after
    approval or an explicit automation rule.
    """

    def __init__(
        self,
        *,
        api_key: str,
        from_email: str,
        base_url: str = "https://api.resend.com",
        timeout_seconds: float = 30.0,
    ) -> None:
        key = (api_key or "").strip()
        if not key:
            raise ProviderNotConfiguredError(
                "RESEND_API_KEY is required for ResendEmailSenderProvider",
                provider="resend-email-sender",
                operation="init",
            )
        from_addr = (from_email or "").strip()
        if not from_addr:
            raise ProviderNotConfiguredError(
                "RESEND_FROM_EMAIL is required for ResendEmailSenderProvider",
                provider="resend-email-sender",
                operation="init",
            )
        self._api_key = key
        self._from_email = from_addr
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._meta = ProviderMetadata(
            name="resend-email-sender",
            vendor="resend",
            capabilities=frozenset({"send_email"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def send_email(self, request: EmailSendRequest) -> EmailSendResponse:
        if not request.to:
            raise ProviderValidationError(
                "to is required",
                provider="resend-email-sender",
                operation="send_email",
            )
        if not (request.subject or "").strip():
            raise ProviderValidationError(
                "subject is required",
                provider="resend-email-sender",
                operation="send_email",
            )

        payload: dict[str, Any] = {
            "from": request.from_email or self._from_email,
            "to": list(request.to),
            "subject": request.subject,
        }
        if request.body_html:
            payload["html"] = request.body_html
            if request.body_text:
                payload["text"] = request.body_text
        else:
            payload["text"] = request.body_text or ""
        if request.reply_to:
            payload["reply_to"] = request.reply_to
        if request.headers:
            payload["headers"] = dict(request.headers)

        response = request_with_retries(
            method="POST",
            url=f"{self._base_url}/emails",
            provider="resend-email-sender",
            operation="send_email",
            timeout_seconds=request.timeout_seconds or self._timeout,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderValidationError(
                "Resend returned non-JSON",
                provider="resend-email-sender",
                operation="send_email",
            ) from exc

        message_id = data.get("id") if isinstance(data, dict) else None
        if not isinstance(message_id, str) or not message_id.strip():
            raise ProviderValidationError(
                "Resend response missing email id",
                provider="resend-email-sender",
                operation="send_email",
            )

        return EmailSendResponse(
            message_id=message_id.strip(),
            accepted=list(request.to),
            delivery_state=EmailDeliveryState.SENT,
            usage=UsageInfo(
                operation="send_email",
                unit_type="emails",
                units=float(len(request.to)),
                provider="resend-email-sender",
            ),
            raw={"resend": data if isinstance(data, dict) else {}},
        )


class SmtpEmailSenderProvider(EmailSenderProvider):
    """Optional SMTP fallback (local Mailhog / self-hosted / provider SMTP).

    Does not auto-send; callers must only invoke after approval.
    Prefer ResendEmailSenderProvider when RESEND_API_KEY is configured.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int = 587,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = True,
        from_email: str,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not host:
            raise ProviderNotConfiguredError(
                "SMTP host is required",
                provider="smtp-email-sender",
                operation="init",
            )
        if not from_email:
            raise ProviderNotConfiguredError(
                "SMTP from_email is required",
                provider="smtp-email-sender",
                operation="init",
            )
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._from_email = from_email
        self._timeout = timeout_seconds
        self._meta = ProviderMetadata(
            name="smtp-email-sender",
            vendor="smtp",
            capabilities=frozenset({"send_email"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def send_email(self, request: EmailSendRequest) -> EmailSendResponse:
        from_addr = request.from_email or self._from_email
        msg = EmailMessage()
        msg["Subject"] = request.subject
        msg["From"] = from_addr
        msg["To"] = ", ".join(request.to)
        if request.reply_to:
            msg["Reply-To"] = request.reply_to
        for key, value in request.headers.items():
            msg[key] = value
        if request.body_html:
            msg.set_content(request.body_text or "")
            msg.add_alternative(request.body_html, subtype="html")
        else:
            msg.set_content(request.body_text or "")

        message_id = request.headers.get("Message-ID") or f"<{uuid.uuid4().hex}@career-agent.local>"
        if "Message-ID" not in msg:
            msg["Message-ID"] = message_id

        try:
            with smtplib.SMTP(self._host, self._port, timeout=request.timeout_seconds) as smtp:
                if self._use_tls:
                    smtp.starttls()
                if self._username and self._password:
                    smtp.login(self._username, self._password)
                refused = smtp.send_message(msg)
        except OSError as exc:
            raise ProviderUnavailableError(
                f"SMTP send failed: {exc}",
                provider="smtp-email-sender",
                operation="send_email",
            ) from exc

        accepted = [addr for addr in request.to if addr not in (refused or {})]
        return EmailSendResponse(
            message_id=message_id.strip("<>"),
            accepted=accepted,
            delivery_state=EmailDeliveryState.SENT if accepted else EmailDeliveryState.FAILED,
            usage=UsageInfo(
                operation="send_email",
                unit_type="emails",
                units=float(len(accepted)),
                provider="smtp-email-sender",
            ),
            raw={"refused": {str(k): str(v) for k, v in (refused or {}).items()}},
        )


class OptionalSesEmailSenderProvider(EmailSenderProvider):
    """OPTIONAL Amazon SES-compatible stub — not required for CI or default setup.

    Marked optional: does not perform real SES domain verification.
    Raises ProviderNotConfiguredError unless explicitly enabled with credentials.
    Prefer ResendEmailSenderProvider, SmtpEmailSenderProvider, or MockEmailSenderProvider.
    """

    def __init__(
        self,
        *,
        region: str = "",
        access_key_id: str = "",
        secret_access_key: str = "",
        from_email: str = "",
        enabled: bool = False,
    ) -> None:
        self._enabled = enabled and bool(
            region and access_key_id and secret_access_key and from_email
        )
        self._meta = ProviderMetadata(
            name="optional-ses-email-sender",
            vendor="aws-ses-optional",
            capabilities=frozenset({"send_email"}) if self._enabled else frozenset(),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def send_email(self, request: EmailSendRequest) -> EmailSendResponse:
        if not self._enabled:
            raise ProviderNotConfiguredError(
                "Optional SES adapter is disabled. Use Resend, Mock, or SMTP. "
                "Real SES requires verified domain/identity (human intervention).",
                provider="optional-ses-email-sender",
                operation="send_email",
            )
        raise ProviderNotConfiguredError(
            "Optional SES adapter is a stub only — wire boto3 + verified identity "
            "before production use. Prefer Resend for default outbound email.",
            provider="optional-ses-email-sender",
            operation="send_email",
        )
