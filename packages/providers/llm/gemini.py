"""Gemini LLMProvider using google-genai SDK with native response_schema."""

from __future__ import annotations

import logging
import time
from typing import Any

from google import genai
from google.genai import types

from packages.providers.base import ProviderMetadata, UsageInfo
from packages.providers.exceptions import (
    ProviderAuthError,
    ProviderError,
    ProviderNotConfiguredError,
    ProviderRateLimitDeferError,
    ProviderRateLimitError,
    ProviderStructuredOutputError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from packages.providers.http_utils import _backoff_seconds
from packages.providers.llm.base import LLMProvider, LLMRequest, LLMResponse
from packages.providers.llm.gemini_config import (
    GEMINI_DEFAULT_MODEL,
    GEMINI_EXTRACTION_MODEL,
)
from packages.providers.llm.gemini_rate_limiter import (
    GeminiRateLimiter,
    InMemoryGeminiRateLimiter,
    RateLimitSnapshot,
)

_PROVIDER_NAME = "gemini-llm"
logger = logging.getLogger("career.providers.gemini")


def _extract_status_code(exc: Exception) -> int | None:
    for attr in ("code", "status_code"):
        value = getattr(exc, attr, None)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    response = getattr(exc, "response", None)
    if response is not None:
        status = getattr(response, "status_code", None)
        if status is not None:
            try:
                return int(status)
            except (TypeError, ValueError):
                pass
    return None


def classify_gemini_error(exc: Exception, *, operation: str) -> ProviderError:
    """Map google-genai SDK errors to shared provider exceptions."""
    message = str(exc)
    details: dict[str, Any] = {"raw_body": message[:8000]}
    status = _extract_status_code(exc)
    if status is not None:
        details["status_code"] = status

    lower = message.lower()
    if status == 400 and (
        "json" in lower or "schema" in lower or "response_schema" in lower
    ):
        return ProviderStructuredOutputError(
            f"{_PROVIDER_NAME} {operation} structured output failed: {message[:400]}",
            provider=_PROVIDER_NAME,
            operation=operation,
            details={**details, "error_code": "json_validate_failed"},
        )
    if status in {401, 403} or "api key" in lower or "permission denied" in lower:
        return ProviderAuthError(
            f"{_PROVIDER_NAME} auth failed: {message[:400]}",
            provider=_PROVIDER_NAME,
            operation=operation,
            details=details,
        )
    if (
        status in {413, 429}
        or "rate_limit_exceeded" in lower
        or "rate limit" in lower
        or "quota" in lower
        or "resource exhausted" in lower
    ):
        return ProviderRateLimitError(
            f"{_PROVIDER_NAME} rate limited: {message[:400]}",
            provider=_PROVIDER_NAME,
            operation=operation,
            details=details,
        )
    if status is not None and status >= 500:
        return ProviderUnavailableError(
            f"{_PROVIDER_NAME} unavailable ({status}): {message[:400]}",
            provider=_PROVIDER_NAME,
            operation=operation,
            details=details,
        )
    if "timeout" in lower or "deadline exceeded" in lower:
        return ProviderTimeoutError(
            f"{_PROVIDER_NAME} timed out: {message[:400]}",
            provider=_PROVIDER_NAME,
            operation=operation,
            details=details,
        )
    return ProviderError(
        f"{_PROVIDER_NAME} {operation} failed: {message[:400]}",
        provider=_PROVIDER_NAME,
        operation=operation,
        details=details,
    )


def _is_transient_retryable(error: ProviderError) -> bool:
    return isinstance(error, (ProviderUnavailableError, ProviderTimeoutError))


def _is_api_rate_limit(error: ProviderError) -> bool:
    if not isinstance(error, ProviderRateLimitError):
        return False
    status = error.details.get("status_code")
    if status == 429:
        return True
    message = str(error).lower()
    return "rate_limit_exceeded" in message or "rate limit" in message


def _is_structured_request(request: LLMRequest) -> bool:
    return bool(
        request.response_schema_model is not None
        or request.json_schema is not None
        or request.response_format == "json"
    )


def _build_contents(request: LLMRequest) -> list[types.Content]:
    contents: list[types.Content] = []
    for message in request.messages:
        if message.role == "system":
            continue
        role = "model" if message.role == "assistant" else "user"
        contents.append(
            types.Content(role=role, parts=[types.Part.from_text(text=message.content)])
        )
    return contents


def _build_config(request: LLMRequest) -> types.GenerateContentConfig:
    config_kwargs: dict[str, Any] = {"temperature": request.temperature}
    if request.max_tokens is not None:
        config_kwargs["max_output_tokens"] = request.max_tokens

    system_parts = [m.content for m in request.messages if m.role == "system"]
    if system_parts:
        config_kwargs["system_instruction"] = "\n\n".join(system_parts)

    if _is_structured_request(request):
        config_kwargs["response_mime_type"] = "application/json"
        if request.response_schema_model is not None:
            config_kwargs["response_schema"] = request.response_schema_model
        elif request.json_schema is not None:
            config_kwargs["response_json_schema"] = request.json_schema

    return types.GenerateContentConfig(**config_kwargs)


def _usage_extra(
    *,
    snapshot: RateLimitSnapshot,
    model: str,
    prompt_tokens: float,
    completion_tokens: float,
) -> dict[str, Any]:
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "model": model,
        "requests_this_minute": snapshot.requests_this_minute,
        "rpm_limit": snapshot.rpm_limit,
        "gemini_tier": snapshot.gemini_tier,
        "rpm_minute_bucket": snapshot.minute_bucket,
    }


class GeminiLLMProvider(LLMProvider):
    """Gemini adapter with native Pydantic response_schema structured output."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = GEMINI_DEFAULT_MODEL,
        extraction_model: str = GEMINI_EXTRACTION_MODEL,
        max_retries: int = 3,
        rate_limit_max_retries: int = 3,
        default_timeout_seconds: float = 60.0,
        rate_limiter: GeminiRateLimiter | None = None,
        gemini_tier: str = "free",
        rpm_limit: int = 10,
        client: genai.Client | None = None,
        sleep_fn: Any = time.sleep,
    ) -> None:
        key = (api_key or "").strip()
        if not key:
            raise ProviderNotConfiguredError(
                "GEMINI_API_KEY is required for GeminiLLMProvider",
                provider=_PROVIDER_NAME,
            )
        self._api_key = key
        self._model = model
        self._extraction_model = extraction_model
        self._max_retries = max_retries
        self._rate_limit_max_retries = rate_limit_max_retries
        self._default_timeout = default_timeout_seconds
        self._client = client
        self._sleep = sleep_fn
        self._rate_limiter = rate_limiter or InMemoryGeminiRateLimiter(
            rpm_limit=rpm_limit,
            gemini_tier=gemini_tier,
            sleep_fn=sleep_fn,
        )
        self._gemini_tier = gemini_tier
        self._rpm_limit = rpm_limit
        self._meta = ProviderMetadata(
            name=_PROVIDER_NAME,
            vendor="google",
            capabilities=frozenset({"chat", "structured", "json", "json_schema"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def _select_model(self, request: LLMRequest) -> str:
        if request.model:
            return request.model
        if _is_structured_request(request):
            return self._extraction_model
        return self._model

    def _client_instance(self, timeout_seconds: float) -> genai.Client:
        if self._client is not None:
            return self._client
        return genai.Client(
            api_key=self._api_key,
            http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),
        )

    def complete(self, request: LLMRequest) -> LLMResponse:
        started = time.perf_counter()
        model = self._select_model(request)
        timeout_seconds = request.timeout_seconds or self._default_timeout
        contents = _build_contents(request)
        config = _build_config(request)
        client = self._client_instance(timeout_seconds)

        rate_limit_attempt = 0
        transient_attempt = 0
        response: Any | None = None
        snapshot = self._rate_limiter.current_snapshot()

        while True:
            snapshot = self._rate_limiter.acquire()
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
                break
            except Exception as exc:
                classified = classify_gemini_error(exc, operation="complete")

                if _is_api_rate_limit(classified):
                    if rate_limit_attempt < self._rate_limit_max_retries:
                        delay = _backoff_seconds(rate_limit_attempt)
                        logger.warning(
                            "gemini_429_backoff attempt=%d/%d delay=%.2fs",
                            rate_limit_attempt + 1,
                            self._rate_limit_max_retries,
                            delay,
                        )
                        self._sleep(delay)
                        rate_limit_attempt += 1
                        continue
                    raise ProviderRateLimitDeferError(
                        f"{_PROVIDER_NAME} rate limit exceeded after "
                        f"{self._rate_limit_max_retries} backoff retries",
                        provider=_PROVIDER_NAME,
                        operation="complete",
                        details={
                            **classified.details,
                            "rate_limit_retries": rate_limit_attempt,
                            "requests_this_minute": snapshot.requests_this_minute,
                            "rpm_limit": snapshot.rpm_limit,
                            "gemini_tier": snapshot.gemini_tier,
                        },
                    ) from exc

                if _is_transient_retryable(classified) and transient_attempt < self._max_retries:
                    delay = _backoff_seconds(transient_attempt)
                    self._sleep(delay)
                    transient_attempt += 1
                    continue

                raise classified from exc

        if response is None:
            raise ProviderValidationError(
                "Gemini returned no response",
                provider=_PROVIDER_NAME,
                operation="complete",
            )

        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            raise ProviderValidationError(
                "Gemini response missing candidates",
                provider=_PROVIDER_NAME,
                operation="complete",
                details={"raw_body": str(response)[:8000]},
            )

        content = response.text or ""
        usage_meta = getattr(response, "usage_metadata", None)
        prompt_tokens = float(getattr(usage_meta, "prompt_token_count", 0) or 0)
        completion_tokens = float(getattr(usage_meta, "candidates_token_count", 0) or 0)
        finish_reason = str(getattr(candidates[0], "finish_reason", None) or "stop")

        logger.info(
            "gemini_complete model=%s rpm=%d/%d tier=%s tokens=%.0f",
            model,
            snapshot.requests_this_minute,
            snapshot.rpm_limit,
            snapshot.gemini_tier,
            prompt_tokens + completion_tokens,
        )

        return LLMResponse(
            content=content,
            model=model,
            finish_reason=finish_reason,
            usage=UsageInfo(
                operation="complete",
                unit_type="tokens",
                units=prompt_tokens + completion_tokens,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                provider=_PROVIDER_NAME,
                extra=_usage_extra(
                    snapshot=snapshot,
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                ),
            ),
        )
