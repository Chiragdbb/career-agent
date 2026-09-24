"""Upstash QStash publish + receiver signature verification."""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Any

import httpx
import jwt


def publish_json(*, token: str, destination_url: str, body: dict[str, Any]) -> str:
    if not token.strip():
        raise ValueError("QSTASH_TOKEN is required")
    if not destination_url.strip():
        raise ValueError("destination_url is required")

    url = f"https://qstash.upstash.io/v2/publish/{destination_url}"
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()

    message_id = data.get("messageId") or data.get("message_id")
    if not message_id:
        raise RuntimeError(f"QStash publish missing messageId: {data!r}")
    return str(message_id)


def _body_hash_matches(claim: str, body: bytes) -> bool:
    claim_stripped = claim.rstrip("=")
    digest = hashlib.sha256(body).digest()
    generated = base64.urlsafe_b64encode(digest).decode()
    generated_stripped = generated.rstrip("=")
    return generated_stripped == claim_stripped or generated == claim


def _verify_jwt_with_key(
    *,
    jwt_token: str,
    signing_key: str,
    body: bytes,
    url: str,
) -> bool:
    parts = jwt_token.split(".")
    if len(parts) != 3:
        return False

    header_b64, payload_b64, signature_b64 = parts
    message = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected_sig = base64.urlsafe_b64encode(
        hmac.new(signing_key.encode("utf-8"), message, digestmod=hashlib.sha256).digest()
    ).decode()

    if expected_sig != signature_b64 and f"{signature_b64}=" != expected_sig:
        return False

    try:
        payload = jwt.decode(jwt_token, options={"verify_signature": False})
    except jwt.PyJWTError:
        return False

    if not isinstance(payload, dict):
        return False

    if payload.get("iss") != "Upstash":
        return False

    sub = payload.get("sub")
    if not isinstance(sub, str):
        return False
    if sub.rstrip("/") != url.rstrip("/"):
        return False

    now = time.time()
    try:
        exp = float(payload["exp"])
        nbf = float(payload["nbf"])
    except (KeyError, TypeError, ValueError):
        return False

    if now > exp or now < nbf:
        return False

    body_claim = payload.get("body")
    if body_claim is None:
        return False
    if not isinstance(body_claim, str):
        return False
    if not _body_hash_matches(body_claim, body):
        return False

    return True


def verify_upstash_signature(
    *,
    signing_keys: list[str],
    signature_header: str,
    body: bytes,
    url: str,
) -> bool:
    """Verify Upstash-Signature JWT (HS256). Returns False on any failure."""
    if not signature_header or not signature_header.strip():
        return False

    signature = signature_header.strip()
    for key in signing_keys:
        if not key or not key.strip():
            continue
        try:
            if _verify_jwt_with_key(
                jwt_token=signature,
                signing_key=key.strip(),
                body=body,
                url=url,
            ):
                return True
        except Exception:
            continue
    return False
