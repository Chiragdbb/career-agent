"""MailboxProvider — optional inbound mailbox (Gmail/Outlook) abstraction.

OAuth is NOT required for CI. Mock/stub only unless credentials already exist.
Encrypted token storage is designed here; encryption key comes from env.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
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
from packages.providers.exceptions import ProviderNotConfiguredError


class MailboxProviderKind(StrEnum):
    mock = "mock"
    gmail = "gmail"
    outlook = "outlook"


class MailboxConnectionStatus(StrEnum):
    disconnected = "disconnected"
    connected = "connected"
    expired = "expired"
    error = "error"


class EncryptedTokenBlob(BaseModel):
    """Opaque encrypted OAuth/refresh token payload for durable storage.

    Design (no live OAuth required):
    - Encrypt with Fernet-like HMAC+XOR fallback when CRYPTOGRAPHY_KEY is set
      as a URL-safe base64 32-byte key, OR store ciphertext via simple
      HMAC-SHA256 keyed XOR for local stub (NOT production-grade).
    - Persist `ciphertext`, `nonce`, `key_id`, `provider` on user settings /
      a future `mailbox_connections` table.
    - Never log plaintext tokens.
    """

    provider: MailboxProviderKind
    ciphertext: str
    nonce: str
    key_id: str = "local-v1"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def encrypt_token(plaintext: str, *, key: bytes | None = None) -> EncryptedTokenBlob:
    """Encrypt a token for storage. Stub crypto for local/dev; swap for Fernet in prod."""
    raw_key = key or _load_token_key()
    nonce = os.urandom(16)
    digest = hmac.new(raw_key, nonce + plaintext.encode("utf-8"), hashlib.sha256).digest()
    # XOR pad (dev stub) — production should use cryptography.Fernet.
    pt = plaintext.encode("utf-8")
    pad = hmac.new(raw_key, nonce, hashlib.sha256).digest()
    while len(pad) < len(pt):
        pad += hmac.new(raw_key, pad, hashlib.sha256).digest()
    cipher = bytes(a ^ b for a, b in zip(pt, pad[: len(pt)], strict=True))
    return EncryptedTokenBlob(
        provider=MailboxProviderKind.mock,
        ciphertext=base64.urlsafe_b64encode(cipher + digest[:16]).decode("ascii"),
        nonce=base64.urlsafe_b64encode(nonce).decode("ascii"),
        key_id="local-v1",
    )


def decrypt_token(blob: EncryptedTokenBlob, *, key: bytes | None = None) -> str:
    raw_key = key or _load_token_key()
    nonce = base64.urlsafe_b64decode(blob.nonce.encode("ascii"))
    raw = base64.urlsafe_b64decode(blob.ciphertext.encode("ascii"))
    cipher, _mac = raw[:-16], raw[-16:]
    pad = hmac.new(raw_key, nonce, hashlib.sha256).digest()
    while len(pad) < len(cipher):
        pad += hmac.new(raw_key, pad, hashlib.sha256).digest()
    pt = bytes(a ^ b for a, b in zip(cipher, pad[: len(cipher)], strict=True))
    return pt.decode("utf-8")


def _load_token_key() -> bytes:
    env = (os.getenv("MAILBOX_TOKEN_ENCRYPTION_KEY") or "").strip()
    if env:
        try:
            return base64.urlsafe_b64decode(env.encode("ascii"))
        except Exception:
            return hashlib.sha256(env.encode("utf-8")).digest()
    # Deterministic local-only key — replace in production.
    return hashlib.sha256(b"career-agent-dev-mailbox-key").digest()


class MailboxConnectionInfo(BaseModel):
    user_id: UUID
    provider: MailboxProviderKind
    status: MailboxConnectionStatus
    email_address: str | None = None
    scopes: list[str] = Field(default_factory=list)
    connected_at: datetime | None = None
    error: str | None = None
    has_encrypted_token: bool = False


class MailboxListRequest(TimeoutMixin):
    user_id: UUID
    query: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class MailboxMessage(BaseModel):
    message_id: str
    subject: str | None = None
    from_address: str | None = None
    snippet: str | None = None
    received_at: datetime | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class MailboxListResponse(BaseModel):
    messages: list[MailboxMessage]
    usage: UsageInfo


class MailboxProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError

    @abstractmethod
    def get_connection_status(self, user_id: UUID) -> MailboxConnectionInfo:
        raise NotImplementedError

    @abstractmethod
    def list_messages(self, request: MailboxListRequest) -> MailboxListResponse:
        raise NotImplementedError

    @abstractmethod
    def store_encrypted_token(
        self, user_id: UUID, blob: EncryptedTokenBlob, *, email_address: str | None = None
    ) -> MailboxConnectionInfo:
        raise NotImplementedError

    @abstractmethod
    def disconnect(self, user_id: UUID) -> MailboxConnectionInfo:
        raise NotImplementedError


class MockMailboxProvider(MailboxProvider):
    """In-memory mailbox + connection status for CI and local stub."""

    def __init__(
        self,
        *,
        fail_with: Exception | None = None,
        simulate_timeout: bool = False,
        latency_ms: float = 2.0,
    ) -> None:
        self._connections: dict[UUID, MailboxConnectionInfo] = {}
        self._tokens: dict[UUID, EncryptedTokenBlob] = {}
        self._messages: dict[UUID, list[MailboxMessage]] = {}
        self._behavior = MockBehavior(
            fail_with=fail_with,
            simulate_timeout=simulate_timeout,
            latency_ms=latency_ms,
            provider_name="mock-mailbox",
        )
        self._meta = ProviderMetadata(
            name="mock-mailbox",
            vendor="mock",
            capabilities=frozenset(
                {"connection_status", "list_messages", "store_token", "disconnect"}
            ),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def get_connection_status(self, user_id: UUID) -> MailboxConnectionInfo:
        self._behavior.before_call(operation="get_connection_status", timeout_seconds=5.0)
        return self._connections.get(
            user_id,
            MailboxConnectionInfo(
                user_id=user_id,
                provider=MailboxProviderKind.mock,
                status=MailboxConnectionStatus.disconnected,
            ),
        )

    def list_messages(self, request: MailboxListRequest) -> MailboxListResponse:
        self._behavior.before_call(
            operation="list_messages", timeout_seconds=request.timeout_seconds
        )
        status = self.get_connection_status(request.user_id)
        if status.status != MailboxConnectionStatus.connected:
            return MailboxListResponse(
                messages=[],
                usage=self._behavior.usage(operation="list_messages", unit_type="messages", units=0),
            )
        msgs = list(self._messages.get(request.user_id, []))[: request.limit]
        return MailboxListResponse(
            messages=msgs,
            usage=self._behavior.usage(
                operation="list_messages", unit_type="messages", units=float(len(msgs))
            ),
        )

    def store_encrypted_token(
        self, user_id: UUID, blob: EncryptedTokenBlob, *, email_address: str | None = None
    ) -> MailboxConnectionInfo:
        self._behavior.before_call(operation="store_encrypted_token", timeout_seconds=5.0)
        self._tokens[user_id] = blob
        info = MailboxConnectionInfo(
            user_id=user_id,
            provider=blob.provider,
            status=MailboxConnectionStatus.connected,
            email_address=email_address,
            scopes=["mail.read"],
            connected_at=datetime.now(timezone.utc),
            has_encrypted_token=True,
        )
        self._connections[user_id] = info
        return info

    def disconnect(self, user_id: UUID) -> MailboxConnectionInfo:
        self._behavior.before_call(operation="disconnect", timeout_seconds=5.0)
        self._tokens.pop(user_id, None)
        info = MailboxConnectionInfo(
            user_id=user_id,
            provider=MailboxProviderKind.mock,
            status=MailboxConnectionStatus.disconnected,
            has_encrypted_token=False,
        )
        self._connections[user_id] = info
        return info

    def seed_messages(self, user_id: UUID, messages: list[MailboxMessage]) -> None:
        self._messages[user_id] = list(messages)


class StubGmailMailboxProvider(MailboxProvider):
    """Gmail stub — OAuth not wired. Reports disconnected until keys exist."""

    def __init__(self) -> None:
        self._meta = ProviderMetadata(
            name="stub-gmail-mailbox",
            vendor="google-gmail-optional",
            capabilities=frozenset({"connection_status"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def get_connection_status(self, user_id: UUID) -> MailboxConnectionInfo:
        return MailboxConnectionInfo(
            user_id=user_id,
            provider=MailboxProviderKind.gmail,
            status=MailboxConnectionStatus.disconnected,
            error="Gmail OAuth not configured (intervention required for live connect)",
        )

    def list_messages(self, request: MailboxListRequest) -> MailboxListResponse:
        raise ProviderNotConfiguredError(
            "Gmail OAuth not configured",
            provider="stub-gmail-mailbox",
            operation="list_messages",
        )

    def store_encrypted_token(
        self, user_id: UUID, blob: EncryptedTokenBlob, *, email_address: str | None = None
    ) -> MailboxConnectionInfo:
        raise ProviderNotConfiguredError(
            "Gmail OAuth not configured",
            provider="stub-gmail-mailbox",
            operation="store_encrypted_token",
        )

    def disconnect(self, user_id: UUID) -> MailboxConnectionInfo:
        return self.get_connection_status(user_id)


class StubOutlookMailboxProvider(MailboxProvider):
    """Outlook stub — OAuth not wired."""

    def __init__(self) -> None:
        self._meta = ProviderMetadata(
            name="stub-outlook-mailbox",
            vendor="microsoft-outlook-optional",
            capabilities=frozenset({"connection_status"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def get_connection_status(self, user_id: UUID) -> MailboxConnectionInfo:
        return MailboxConnectionInfo(
            user_id=user_id,
            provider=MailboxProviderKind.outlook,
            status=MailboxConnectionStatus.disconnected,
            error="Outlook OAuth not configured (intervention required for live connect)",
        )

    def list_messages(self, request: MailboxListRequest) -> MailboxListResponse:
        raise ProviderNotConfiguredError(
            "Outlook OAuth not configured",
            provider="stub-outlook-mailbox",
            operation="list_messages",
        )

    def store_encrypted_token(
        self, user_id: UUID, blob: EncryptedTokenBlob, *, email_address: str | None = None
    ) -> MailboxConnectionInfo:
        raise ProviderNotConfiguredError(
            "Outlook OAuth not configured",
            provider="stub-outlook-mailbox",
            operation="store_encrypted_token",
        )

    def disconnect(self, user_id: UUID) -> MailboxConnectionInfo:
        return self.get_connection_status(user_id)
