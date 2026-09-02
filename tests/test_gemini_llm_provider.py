"""Gemini LLMProvider tests (mocked google-genai SDK)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from packages.domain.job_models import ExtractedJob
from packages.domain.extraction_constants import (
    GEMINI_EXTRACTION_CONTENT_MAX_CHARS,
    GEMINI_EXTRACTION_CONTENT_PREFILTER_MAX_CHARS,
    extraction_max_chars_for_provider,
    extraction_prefilter_max_chars_for_provider,
)
from packages.providers.exceptions import (
    ProviderAuthError,
    ProviderNotConfiguredError,
    ProviderRateLimitDeferError,
    ProviderRateLimitError,
)
from packages.providers.llm.base import LLMMessage, LLMRequest
from packages.providers.llm.gemini import GeminiLLMProvider, classify_gemini_error
from packages.providers.llm.gemini_config import gemini_rpm_for_tier
from packages.providers.llm.gemini_rate_limiter import InMemoryGeminiRateLimiter


class _FakeUsage:
    prompt_token_count = 12
    candidates_token_count = 8


class _FakeCandidate:
    finish_reason = "STOP"


class _FakeResponse:
    text = '{"title":"Engineer","url":"https://example.com/job"}'
    candidates = [_FakeCandidate()]
    usage_metadata = _FakeUsage()


class _FakeModels:
    def __init__(self) -> None:
        self.last_kwargs: dict = {}
        self.calls = 0
        self._effects: list[Exception | None] = []

    def set_effects(self, effects: list[Exception | None]) -> None:
        self._effects = list(effects)

    def generate_content(self, **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs
        if self._effects:
            effect = self._effects.pop(0)
            if effect is not None:
                raise effect
        return _FakeResponse()


class _FakeClient:
    def __init__(self) -> None:
        self.models = _FakeModels()


def _provider(
    client: _FakeClient,
    *,
    max_retries: int = 3,
    rate_limit_max_retries: int = 3,
    rpm: int = 100,
    sleep_fn=None,
) -> GeminiLLMProvider:
    limiter = InMemoryGeminiRateLimiter(
        rpm_limit=rpm,
        gemini_tier="free",
        sleep_fn=sleep_fn or (lambda _: None),
    )
    return GeminiLLMProvider(
        api_key="gem-test",
        rate_limiter=limiter,
        max_retries=max_retries,
        rate_limit_max_retries=rate_limit_max_retries,
        client=client,  # type: ignore[arg-type]
        sleep_fn=sleep_fn or (lambda _: None),
    )


def test_gemini_requires_api_key() -> None:
    with pytest.raises(ProviderNotConfiguredError):
        GeminiLLMProvider(api_key="")


def test_gemini_complete_parses_usage() -> None:
    client = _FakeClient()
    response = _provider(client).complete(
        LLMRequest(messages=[LLMMessage(role="user", content="hi")], response_format="json")
    )
    assert '"title"' in response.content
    assert response.usage.units == 20.0
    assert response.usage.extra["prompt_tokens"] == 12.0
    assert response.usage.extra["requests_this_minute"] == 1
    assert response.usage.extra["rpm_limit"] == 100
    assert client.models.last_kwargs["config"].response_mime_type == "application/json"


def test_gemini_uses_flash_lite_for_structured_calls() -> None:
    client = _FakeClient()
    _provider(client).complete(
        LLMRequest(
            messages=[LLMMessage(role="user", content="hi")],
            response_format="json",
            response_schema_model=ExtractedJob,
        )
    )
    assert client.models.last_kwargs["model"] == "gemini-2.5-flash-lite"


def test_gemini_passes_pydantic_response_schema() -> None:
    client = _FakeClient()
    _provider(client).complete(
        LLMRequest(
            messages=[
                LLMMessage(role="system", content="Extract job fields"),
                LLMMessage(role="user", content="URL: https://example.com/job"),
            ],
            response_format="json",
            response_schema_model=ExtractedJob,
        )
    )
    config = client.models.last_kwargs["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_schema is ExtractedJob


def test_gemini_uses_system_instruction_not_user_prefix() -> None:
    client = _FakeClient()
    _provider(client).complete(
        LLMRequest(
            messages=[
                LLMMessage(role="system", content="System rules"),
                LLMMessage(role="user", content="User content"),
            ]
        )
    )
    config = client.models.last_kwargs["config"]
    assert config.system_instruction == "System rules"
    user_content = client.models.last_kwargs["contents"][0]
    assert user_content.parts[0].text == "User content"


def test_gemini_429_backoff_then_success() -> None:
    client = _FakeClient()

    class _RateLimited(Exception):
        code = 429

    client.models.set_effects([_RateLimited("rate_limit_exceeded"), _RateLimited("rate_limit_exceeded"), None])

    sleeps: list[float] = []
    response = _provider(client, rate_limit_max_retries=3, sleep_fn=sleeps.append).complete(
        LLMRequest(messages=[LLMMessage(role="user", content="hi")], response_format="json")
    )
    assert '"title"' in response.content
    assert client.models.calls == 3
    assert len(sleeps) == 2


def test_gemini_429_exhausted_raises_defer_error() -> None:
    client = _FakeClient()

    class _RateLimited(Exception):
        code = 429

    client.models.set_effects([_RateLimited("rate_limit_exceeded")] * 5)

    with pytest.raises(ProviderRateLimitDeferError):
        _provider(client, rate_limit_max_retries=2, sleep_fn=lambda _: None).complete(
            LLMRequest(messages=[LLMMessage(role="user", content="hi")])
        )
    assert client.models.calls == 3


def test_classify_gemini_error_maps_auth() -> None:
    exc = SimpleNamespace(code=403, response=None)
    err = classify_gemini_error(exc, operation="complete")  # type: ignore[arg-type]
    assert isinstance(err, ProviderAuthError)


def test_classify_gemini_error_maps_rate_limit() -> None:
    exc = SimpleNamespace(code=429, response=None)
    err = classify_gemini_error(exc, operation="complete")  # type: ignore[arg-type]
    assert isinstance(err, ProviderRateLimitError)


def test_gemini_tier_rpm_defaults() -> None:
    assert gemini_rpm_for_tier("free") == 10
    assert gemini_rpm_for_tier("paid") == 1000


def test_gemini_extraction_limits_are_high() -> None:
    assert extraction_max_chars_for_provider("gemini-llm") == GEMINI_EXTRACTION_CONTENT_MAX_CHARS
    assert extraction_prefilter_max_chars_for_provider("gemini-llm") == (
        GEMINI_EXTRACTION_CONTENT_PREFILTER_MAX_CHARS
    )
    assert GEMINI_EXTRACTION_CONTENT_MAX_CHARS > 100_000


def test_redis_rate_limiter_blocks_over_quota() -> None:
    class _FakeRedis:
        def __init__(self) -> None:
            self._data: dict[str, int] = {}

        def incr(self, key: str) -> int:
            self._data[key] = self._data.get(key, 0) + 1
            return self._data[key]

        def decr(self, key: str) -> int:
            self._data[key] = max(0, self._data.get(key, 0) - 1)
            return self._data[key]

        def expire(self, key: str, ttl: int) -> None:
            return None

        def set(self, key: str, value: int, ex: int | None = None) -> None:
            self._data[key] = value

        def get(self, key: str) -> int | None:
            return self._data.get(key)

    from packages.providers.llm.gemini_rate_limiter import RedisGeminiRateLimiter

    redis = _FakeRedis()
    limiter = RedisGeminiRateLimiter(redis, rpm_limit=2, gemini_tier="free", sleep_fn=lambda _: None)
    s1 = limiter.acquire()
    s2 = limiter.acquire()
    assert s1.requests_this_minute == 1
    assert s2.requests_this_minute == 2
