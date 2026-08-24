"""Supabase JWT verification via JWKS (no shared JWT secret required)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx
import jwt
from jwt import PyJWKClient

from packages.domain.exceptions import AuthenticationError


@dataclass(frozen=True)
class AuthClaims:
    """Verified claims from a Supabase access token."""

    subject: str
    email: str | None = None
    role: str | None = None
    raw: dict[str, Any] | None = None


class JwtVerifier(Protocol):
    def verify(self, token: str) -> AuthClaims: ...


class SupabaseJwksVerifier:
    """Verify Supabase access tokens using the project's JWKS endpoint.

    JWKS URL: ``{SUPABASE_URL}/auth/v1/.well-known/jwks.json``
    Expected issuer: ``{SUPABASE_URL}/auth/v1``
    Audience: ``authenticated``
    """

    def __init__(
        self,
        supabase_url: str,
        *,
        http_timeout_seconds: float = 5.0,
        jwks_client: PyJWKClient | None = None,
    ) -> None:
        base = supabase_url.rstrip("/")
        if not base:
            raise ValueError("supabase_url must not be blank")
        self._issuer = f"{base}/auth/v1"
        self._audience = "authenticated"
        self._jwks_url = f"{self._issuer}/.well-known/jwks.json"
        self._jwks_client = jwks_client or PyJWKClient(
            self._jwks_url,
            cache_keys=True,
            lifespan=3600,
            timeout=http_timeout_seconds,
        )

    @property
    def jwks_url(self) -> str:
        return self._jwks_url

    def verify(self, token: str) -> AuthClaims:
        token = (token or "").strip()
        if not token:
            raise AuthenticationError("Missing bearer token")

        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256", "EdDSA"],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "sub", "iat"]},
            )
        except jwt.PyJWTError as exc:
            raise AuthenticationError("Invalid or expired access token") from exc
        except (httpx.HTTPError, TimeoutError, OSError) as exc:
            raise AuthenticationError("Unable to verify access token") from exc

        subject = payload.get("sub")
        if not subject or not isinstance(subject, str):
            raise AuthenticationError("Token missing subject")

        return AuthClaims(
            subject=subject,
            email=payload.get("email") if isinstance(payload.get("email"), str) else None,
            role=payload.get("role") if isinstance(payload.get("role"), str) else None,
            raw=dict(payload),
        )


class StaticJwtVerifier:
    """Test double: maps opaque tokens to claims without network or crypto."""

    def __init__(self, tokens: dict[str, AuthClaims] | None = None) -> None:
        self._tokens = dict(tokens or {})

    def register(self, token: str, claims: AuthClaims) -> None:
        self._tokens[token] = claims

    def verify(self, token: str) -> AuthClaims:
        token = (token or "").strip()
        if token not in self._tokens:
            raise AuthenticationError("Invalid or expired access token")
        return self._tokens[token]
