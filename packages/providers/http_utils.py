"""Shared HTTP retry / rate-limit helpers for provider adapters."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import Any

import httpx

from packages.providers.exceptions import (
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


def classify_http_error(
    *,
    status_code: int,
    body: str,
    provider: str,
    operation: str,
) -> ProviderError:
    detail = (body or "")[:400]
    if status_code in {401, 403}:
        return ProviderAuthError(
            f"{provider} auth failed ({status_code}): {detail}",
            provider=provider,
            operation=operation,
        )
    if status_code == 429:
        return ProviderRateLimitError(
            f"{provider} rate limited: {detail}",
            provider=provider,
            operation=operation,
        )
    if status_code >= 500:
        return ProviderUnavailableError(
            f"{provider} unavailable ({status_code}): {detail}",
            provider=provider,
            operation=operation,
        )
    return ProviderError(
        f"{provider} {operation} failed ({status_code}): {detail}",
        provider=provider,
        operation=operation,
    )


def request_with_retries(
    *,
    method: str,
    url: str,
    provider: str,
    operation: str,
    timeout_seconds: float,
    max_retries: int = 3,
    headers: dict[str, str] | None = None,
    json: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    content: bytes | None = None,
    retryable_statuses: frozenset[int] = frozenset({408, 429, 500, 502, 503, 504}),
    sleep_fn: Callable[[float], None] = time.sleep,
) -> httpx.Response:
    """Perform an HTTP request with bounded retries and error classification."""
    attempt = 0
    last_error: Exception | None = None
    while attempt <= max_retries:
        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.request(
                    method,
                    url,
                    headers=headers,
                    json=json,
                    params=params,
                    content=content,
                )
            if response.status_code < 400:
                return response
            if response.status_code in retryable_statuses and attempt < max_retries:
                sleep_fn(_backoff_seconds(attempt, response))
                attempt += 1
                continue
            raise classify_http_error(
                status_code=response.status_code,
                body=response.text,
                provider=provider,
                operation=operation,
            )
        except httpx.TimeoutException as exc:
            last_error = ProviderTimeoutError(
                f"{provider} timed out after {timeout_seconds}s",
                provider=provider,
                operation=operation,
            )
            if attempt >= max_retries:
                raise last_error from exc
            sleep_fn(_backoff_seconds(attempt))
            attempt += 1
        except httpx.HTTPError as exc:
            last_error = ProviderUnavailableError(
                f"{provider} request failed: {exc}",
                provider=provider,
                operation=operation,
            )
            if attempt >= max_retries:
                raise last_error from exc
            sleep_fn(_backoff_seconds(attempt))
            attempt += 1
    assert last_error is not None
    raise last_error


def _backoff_seconds(attempt: int, response: httpx.Response | None = None) -> float:
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), 30.0)
            except ValueError:
                pass
    base = min(2**attempt, 8)
    return base + random.uniform(0, 0.25)
