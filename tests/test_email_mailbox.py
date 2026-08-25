"""STEP 26–27 — EmailSender + Mailbox provider tests."""

from __future__ import annotations

import json
import uuid

import pytest

from packages.providers.email_sender import (
    EmailDeliveryState,
    EmailSendRequest,
    MockEmailSenderProvider,
    OptionalSesEmailSenderProvider,
    ResendEmailSenderProvider,
)
from packages.providers.exceptions import (
    ProviderNotConfiguredError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from packages.providers.factory import ProviderSettings, create_email_sender_provider
from packages.providers.mailbox import (
    MailboxConnectionStatus,
    MockMailboxProvider,
    decrypt_token,
    encrypt_token,
)


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | str, headers: dict | None = None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = payload if isinstance(payload, str) else json.dumps(payload)

    def json(self):
        if isinstance(self._payload, str):
            raise ValueError("not json")
        return self._payload


def test_mock_email_sender_delivery_state() -> None:
    sender = MockEmailSenderProvider()
    resp = sender.send_email(
        EmailSendRequest(to=["a@example.com"], subject="Hi", body_text="Hello")
    )
    assert resp.delivery_state == EmailDeliveryState.SENT
    assert resp.message_id
    assert resp.accepted == ["a@example.com"]


def test_resend_requires_api_key_and_from() -> None:
    with pytest.raises(ProviderNotConfiguredError, match="RESEND_API_KEY"):
        ResendEmailSenderProvider(api_key="", from_email="noreply@example.com")
    with pytest.raises(ProviderNotConfiguredError, match="RESEND_FROM_EMAIL"):
        ResendEmailSenderProvider(api_key="re_test", from_email="")


def test_resend_send_maps_to_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_request(**kwargs):
        captured.update(kwargs)
        return _FakeResponse(200, {"id": "re_msg_abc123"})

    monkeypatch.setattr(
        "packages.providers.email_sender.request_with_retries",
        fake_request,
    )
    sender = ResendEmailSenderProvider(
        api_key="re_test",
        from_email="noreply@example.com",
    )
    resp = sender.send_email(
        EmailSendRequest(
            to=["a@example.com"],
            subject="Hello",
            body_text="Plain",
            body_html="<p>Plain</p>",
            reply_to="me@example.com",
        )
    )
    assert resp.delivery_state == EmailDeliveryState.SENT
    assert resp.message_id == "re_msg_abc123"
    assert resp.accepted == ["a@example.com"]
    assert resp.usage.provider == "resend-email-sender"
    assert resp.usage.unit_type == "emails"
    assert resp.usage.units == 1.0
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["headers"]["Authorization"] == "Bearer re_test"
    assert captured["json"]["from"] == "noreply@example.com"
    assert captured["json"]["to"] == ["a@example.com"]
    assert captured["json"]["html"] == "<p>Plain</p>"
    assert captured["json"]["text"] == "Plain"
    assert captured["json"]["reply_to"] == "me@example.com"


def test_resend_rate_limit_classified(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_request(**kwargs):
        raise ProviderRateLimitError(
            "rate", provider="resend-email-sender", operation="send_email"
        )

    monkeypatch.setattr(
        "packages.providers.email_sender.request_with_retries",
        fake_request,
    )
    sender = ResendEmailSenderProvider(api_key="re_test", from_email="n@example.com")
    with pytest.raises(ProviderRateLimitError):
        sender.send_email(
            EmailSendRequest(to=["a@example.com"], subject="x", body_text="y")
        )


def test_resend_timeout_classified(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_request(**kwargs):
        raise ProviderTimeoutError(
            "timeout", provider="resend-email-sender", operation="send_email"
        )

    monkeypatch.setattr(
        "packages.providers.email_sender.request_with_retries",
        fake_request,
    )
    sender = ResendEmailSenderProvider(api_key="re_test", from_email="n@example.com")
    with pytest.raises(ProviderTimeoutError):
        sender.send_email(
            EmailSendRequest(to=["a@example.com"], subject="x", body_text="y")
        )


def test_factory_selects_resend_when_api_key_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SES_ENABLED", raising=False)
    settings = ProviderSettings(
        resend_api_key="re_test",
        resend_from_email="noreply@example.com",
    )
    provider = create_email_sender_provider(settings)
    assert provider.metadata.vendor == "resend"
    assert provider.metadata.name == "resend-email-sender"


def test_factory_falls_back_to_mock_without_resend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SES_ENABLED", raising=False)
    settings = ProviderSettings(resend_api_key="", resend_from_email="")
    provider = create_email_sender_provider(settings)
    assert provider.metadata.vendor == "mock"


def test_optional_ses_requires_intervention() -> None:
    ses = OptionalSesEmailSenderProvider(enabled=False)
    with pytest.raises(ProviderNotConfiguredError, match="intervention|disabled"):
        ses.send_email(EmailSendRequest(to=["a@example.com"], subject="x", body_text="y"))


def test_mailbox_encrypt_decrypt_roundtrip() -> None:
    blob = encrypt_token("refresh-token-secret")
    assert blob.ciphertext
    assert decrypt_token(blob) == "refresh-token-secret"


def test_mailbox_connection_status_stub() -> None:
    mb = MockMailboxProvider()
    user_id = uuid.uuid4()
    status = mb.get_connection_status(user_id)
    assert status.status == MailboxConnectionStatus.disconnected

    blob = encrypt_token("tok")
    connected = mb.store_encrypted_token(user_id, blob, email_address="me@example.com")
    assert connected.status == MailboxConnectionStatus.connected
    assert connected.has_encrypted_token is True

    disconnected = mb.disconnect(user_id)
    assert disconnected.status == MailboxConnectionStatus.disconnected
