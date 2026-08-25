"""Hunter.io EmailFinderProvider / EmailVerifierProvider adapters.

Requires HUNTER_API_KEY. Without a key, factory falls back to mocks.
Never invent addresses — only return what Hunter reports.
"""

from __future__ import annotations

from typing import Any

from packages.providers.base import ProviderMetadata, UsageInfo
from packages.providers.email_finder import (
    EmailCandidate,
    EmailFinderProvider,
    EmailFindRequest,
    EmailFindResponse,
)
from packages.providers.email_verifier import (
    EmailVerificationStatus,
    EmailVerifierProvider,
    EmailVerifyRequest,
    EmailVerifyResponse,
)
from packages.providers.exceptions import (
    ProviderNotConfiguredError,
    ProviderValidationError,
)
from packages.providers.http_utils import request_with_retries


class HunterEmailFinderProvider(EmailFinderProvider):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.hunter.io/v2",
        timeout_seconds: float = 30.0,
    ) -> None:
        key = (api_key or "").strip()
        if not key:
            raise ProviderNotConfiguredError(
                "HUNTER_API_KEY is required for HunterEmailFinderProvider",
                provider="hunter-email-finder",
            )
        self._api_key = key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._meta = ProviderMetadata(
            name="hunter-email-finder",
            vendor="hunter",
            capabilities=frozenset({"email_find"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def find_email(self, request: EmailFindRequest) -> EmailFindResponse:
        parts = request.full_name.strip().split()
        first = parts[0] if parts else ""
        last = parts[-1] if len(parts) > 1 else ""
        params: dict[str, Any] = {
            "domain": request.company_domain,
            "first_name": first,
            "last_name": last,
            "api_key": self._api_key,
        }
        response = request_with_retries(
            method="GET",
            url=f"{self._base_url}/email-finder",
            provider="hunter-email-finder",
            operation="find_email",
            timeout_seconds=request.timeout_seconds or self._timeout,
            params=params,
        )
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderValidationError(
                "Hunter returned non-JSON",
                provider="hunter-email-finder",
                operation="find_email",
            ) from exc

        email_data = data.get("data") or {}
        email = email_data.get("email")
        candidates: list[EmailCandidate] = []
        if isinstance(email, str) and "@" in email:
            score = email_data.get("score")
            try:
                confidence = float(score) / 100.0 if score is not None else 0.5
            except (TypeError, ValueError):
                confidence = 0.5
            candidates.append(
                EmailCandidate(
                    email=email.strip().lower(),
                    confidence=max(0.0, min(confidence, 1.0)),
                    sources=["hunter"],
                )
            )
        return EmailFindResponse(
            candidates=candidates,
            usage=UsageInfo(
                operation="find_email",
                unit_type="lookups",
                units=1.0,
                provider="hunter-email-finder",
            ),
        )


class HunterEmailVerifierProvider(EmailVerifierProvider):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.hunter.io/v2",
        timeout_seconds: float = 30.0,
    ) -> None:
        key = (api_key or "").strip()
        if not key:
            raise ProviderNotConfiguredError(
                "HUNTER_API_KEY is required for HunterEmailVerifierProvider",
                provider="hunter-email-verifier",
            )
        self._api_key = key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._meta = ProviderMetadata(
            name="hunter-email-verifier",
            vendor="hunter",
            capabilities=frozenset({"email_verify"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def verify_email(self, request: EmailVerifyRequest) -> EmailVerifyResponse:
        params = {"email": request.email, "api_key": self._api_key}
        response = request_with_retries(
            method="GET",
            url=f"{self._base_url}/email-verifier",
            provider="hunter-email-verifier",
            operation="verify_email",
            timeout_seconds=request.timeout_seconds or self._timeout,
            params=params,
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderValidationError(
                "Hunter returned non-JSON",
                provider="hunter-email-verifier",
                operation="verify_email",
            ) from exc

        data = payload.get("data") or {}
        result = str(data.get("result") or data.get("status") or "unknown").lower()
        status_map = {
            "deliverable": EmailVerificationStatus.valid,
            "valid": EmailVerificationStatus.valid,
            "undeliverable": EmailVerificationStatus.invalid,
            "invalid": EmailVerificationStatus.invalid,
            "risky": EmailVerificationStatus.risky,
            "unknown": EmailVerificationStatus.unknown,
        }
        status = status_map.get(result, EmailVerificationStatus.unknown)
        score_raw = data.get("score")
        try:
            score = float(score_raw) / 100.0 if score_raw is not None else None
        except (TypeError, ValueError):
            score = None
        return EmailVerifyResponse(
            email=request.email,
            status=status,
            score=score,
            details=str(data.get("result") or result),
            usage=UsageInfo(
                operation="verify_email",
                unit_type="verifications",
                units=1.0,
                provider="hunter-email-verifier",
            ),
        )
