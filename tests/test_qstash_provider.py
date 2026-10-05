"""Unit tests for Upstash QStash publish + signature helpers."""

from __future__ import annotations

import base64
import hashlib
import time
from unittest.mock import MagicMock, patch

import jwt
import pytest

from packages.providers.qstash import (
    cancel_all_messages,
    cancel_message,
    publish_json,
    verify_upstash_signature,
)


def _make_upstash_signature(
    *,
    signing_key: str,
    body: bytes,
    url: str,
    exp_offset: int = 300,
    nbf_offset: int = -10,
) -> str:
    body_hash = base64.urlsafe_b64encode(hashlib.sha256(body).digest()).decode().rstrip("=")
    now = int(time.time())
    payload = {
        "iss": "Upstash",
        "sub": url,
        "exp": now + exp_offset,
        "nbf": now + nbf_offset,
        "iat": now,
        "jti": "jwt_test",
        "body": body_hash,
    }
    return jwt.encode(payload, signing_key, algorithm="HS256")


@patch("packages.providers.qstash.httpx.Client")
def test_publish_json_posts_to_qstash(mock_client_cls: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"messageId": "msg_123"}
    mock_resp.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_resp
    mock_client_cls.return_value = mock_client

    destination = "https://api.example.com/internal/qstash/discover-jobs"
    mid = publish_json(
        token="tok",
        destination_url=destination,
        body={"user_id": "u1"},
    )
    assert mid == "msg_123"

    mock_client.post.assert_called_once()
    args, kwargs = mock_client.post.call_args
    assert args[0] == f"https://qstash.upstash.io/v2/publish/{destination}"
    assert kwargs["headers"]["Authorization"] == "Bearer tok"
    assert kwargs["headers"]["Content-Type"] == "application/json"
    assert kwargs["json"] == {"user_id": "u1"}


def test_publish_json_requires_token() -> None:
    with pytest.raises(ValueError, match="QSTASH_TOKEN"):
        publish_json(token="  ", destination_url="https://example.com/x", body={})


@patch("packages.providers.qstash.httpx.Client")
def test_cancel_message_deletes_pending(mock_client_cls: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.delete.return_value = mock_resp
    mock_client_cls.return_value = mock_client

    assert cancel_message(token="tok", message_id="msg_abc") is True
    mock_client.delete.assert_called_once()
    args, kwargs = mock_client.delete.call_args
    assert args[0] == "https://qstash.upstash.io/v2/messages/msg_abc"
    assert kwargs["headers"]["Authorization"] == "Bearer tok"


@patch("packages.providers.qstash.httpx.Client")
def test_cancel_message_missing_returns_false(mock_client_cls: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 404

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.delete.return_value = mock_resp
    mock_client_cls.return_value = mock_client

    assert cancel_message(token="tok", message_id="msg_missing") is False


@patch("packages.providers.qstash.httpx.Client")
def test_cancel_all_messages_returns_count(mock_client_cls: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 202
    mock_resp.content = b'{"cancelled":3}'
    mock_resp.json.return_value = {"cancelled": 3}
    mock_resp.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.delete.return_value = mock_resp
    mock_client_cls.return_value = mock_client

    assert cancel_all_messages(token="tok") == 3


def test_verify_rejects_empty_signature() -> None:
    assert (
        verify_upstash_signature(
            signing_keys=["sig_xxx"],
            signature_header="",
            body=b"{}",
            url="https://api.example.com/x",
        )
        is False
    )


def test_verify_accepts_valid_signature() -> None:
    body = b'{"user_id":"u1"}'
    url = "https://api.example.com/internal/qstash/discover-jobs"
    key = "test_signing_key_32_chars_minimum!!"
    signature = _make_upstash_signature(signing_key=key, body=body, url=url)

    assert (
        verify_upstash_signature(
            signing_keys=[key],
            signature_header=signature,
            body=body,
            url=url,
        )
        is True
    )


def test_verify_tries_next_signing_key() -> None:
    body = b"{}"
    url = "https://api.example.com/x"
    current_key = "wrong_key_______________________"
    next_key = "next_key________________________"
    signature = _make_upstash_signature(signing_key=next_key, body=body, url=url)

    assert (
        verify_upstash_signature(
            signing_keys=[current_key, next_key],
            signature_header=signature,
            body=body,
            url=url,
        )
        is True
    )


def test_verify_rejects_expired_token() -> None:
    body = b"{}"
    url = "https://api.example.com/x"
    key = "test_signing_key_32_chars_minimum!!"
    signature = _make_upstash_signature(
        signing_key=key,
        body=body,
        url=url,
        exp_offset=-60,
        nbf_offset=-120,
    )

    assert (
        verify_upstash_signature(
            signing_keys=[key],
            signature_header=signature,
            body=body,
            url=url,
        )
        is False
    )


def test_verify_rejects_jwt_missing_body_claim() -> None:
    body = b"{}"
    url = "https://api.example.com/x"
    key = "test_signing_key_32_chars_minimum!!"
    now = int(time.time())
    payload = {
        "iss": "Upstash",
        "sub": url,
        "exp": now + 300,
        "nbf": now - 10,
        "iat": now,
        "jti": "jwt_test_no_body",
    }
    signature = jwt.encode(payload, key, algorithm="HS256")

    assert (
        verify_upstash_signature(
            signing_keys=[key],
            signature_header=signature,
            body=body,
            url=url,
        )
        is False
    )


def test_verify_rejects_body_mismatch() -> None:
    url = "https://api.example.com/x"
    key = "test_signing_key_32_chars_minimum!!"
    signature = _make_upstash_signature(signing_key=key, body=b"{}", url=url)

    assert (
        verify_upstash_signature(
            signing_keys=[key],
            signature_header=signature,
            body=b'{"tampered":true}',
            url=url,
        )
        is False
    )
