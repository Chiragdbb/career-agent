"""Groq, Gemini, and OpenAI LLMProvider adapters.

Structured outputs are validated by domain services before persistence — adapters
return text/JSON strings and surface vendor error details (e.g. failed_generation).
"""

from __future__ import annotations

import json
import time
from typing import Any

from packages.providers.base import ProviderMetadata, UsageInfo
from packages.providers.exceptions import (
    ProviderNotConfiguredError,
    ProviderValidationError,
)
from packages.providers.groq_models import DEFAULT_GROQ_MODEL
from packages.providers.http_utils import request_with_retries
from packages.providers.llm import LLMProvider, LLMRequest, LLMResponse

_PROVIDER_NAME = "groq-llm"
_OPENAI_PROVIDER = "openai-llm"
_GEMINI_PROVIDER = "gemini-llm"


def _build_response_format(request: LLMRequest) -> dict[str, Any] | None:
    if request.json_schema is not None:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": request.json_schema_name or "structured_output",
                "strict": True,
                "schema": request.json_schema,
            },
        }
    if request.response_format == "json":
        return {"type": "json_object"}
    return None


class GroqLLMProvider(LLMProvider):
    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_GROQ_MODEL,
        max_retries: int = 3,
        default_timeout_seconds: float = 60.0,
    ) -> None:
        key = (api_key or "").strip()
        if not key:
            raise ProviderNotConfiguredError(
                "GROQ_API_KEY is required for GroqLLMProvider",
                provider=_PROVIDER_NAME,
            )
        self._api_key = key
        self._model = model
        self._max_retries = max_retries
        self._default_timeout = default_timeout_seconds
        self._meta = ProviderMetadata(
            name=_PROVIDER_NAME,
            vendor="groq",
            capabilities=frozenset({"chat", "structured", "json"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def complete(self, request: LLMRequest) -> LLMResponse:
        started = time.perf_counter()
        model = request.model or self._model
        body: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
        }
        if request.max_tokens is not None:
            body["max_tokens"] = request.max_tokens
        response_format = _build_response_format(request)
        if response_format is not None:
            # Groq supports json_object mode only (no strict json_schema).
            body["response_format"] = {"type": "json_object"}

        response = request_with_retries(
            method="POST",
            url="https://api.groq.com/openai/v1/chat/completions",
            provider=_PROVIDER_NAME,
            operation="complete",
            timeout_seconds=request.timeout_seconds or self._default_timeout,
            max_retries=self._max_retries,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderValidationError(
                "Groq returned non-JSON response",
                provider=_PROVIDER_NAME,
                operation="complete",
                details={"raw_body": response.text[:8000]},
            ) from exc

        choices = data.get("choices") or []
        if not choices:
            raise ProviderValidationError(
                "Groq response missing choices",
                provider=_PROVIDER_NAME,
                operation="complete",
                details={"raw_body": response.text[:8000]},
            )
        message = choices[0].get("message") or {}
        content = message.get("content") or ""
        usage_raw = data.get("usage") or {}
        prompt_tokens = float(usage_raw.get("prompt_tokens") or 0)
        completion_tokens = float(usage_raw.get("completion_tokens") or 0)
        return LLMResponse(
            content=str(content),
            model=str(data.get("model") or model),
            finish_reason=str(choices[0].get("finish_reason") or "stop"),
            usage=UsageInfo(
                operation="complete",
                unit_type="tokens",
                units=prompt_tokens + completion_tokens,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                provider=_PROVIDER_NAME,
                extra={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "model": model,
                },
            ),
        )


class OpenAILLMProvider(LLMProvider):
    """OpenAI chat completions with native json_schema structured outputs."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-4o-mini",
        max_retries: int = 3,
        default_timeout_seconds: float = 90.0,
    ) -> None:
        key = (api_key or "").strip()
        if not key:
            raise ProviderNotConfiguredError(
                "OPENAI_API_KEY is required for OpenAILLMProvider",
                provider=_OPENAI_PROVIDER,
            )
        self._api_key = key
        self._model = model
        self._max_retries = max_retries
        self._default_timeout = default_timeout_seconds
        self._meta = ProviderMetadata(
            name=_OPENAI_PROVIDER,
            vendor="openai",
            capabilities=frozenset({"chat", "structured", "json", "json_schema"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def complete(self, request: LLMRequest) -> LLMResponse:
        started = time.perf_counter()
        model = request.model or self._model
        body: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
        }
        if request.max_tokens is not None:
            body["max_tokens"] = request.max_tokens
        response_format = _build_response_format(request)
        if response_format is not None:
            body["response_format"] = response_format

        response = request_with_retries(
            method="POST",
            url="https://api.openai.com/v1/chat/completions",
            provider=_OPENAI_PROVIDER,
            operation="complete",
            timeout_seconds=request.timeout_seconds or self._default_timeout,
            max_retries=self._max_retries,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderValidationError(
                "OpenAI returned non-JSON response",
                provider=_OPENAI_PROVIDER,
                operation="complete",
                details={"raw_body": response.text[:8000]},
            ) from exc

        choices = data.get("choices") or []
        if not choices:
            raise ProviderValidationError(
                "OpenAI response missing choices",
                provider=_OPENAI_PROVIDER,
                operation="complete",
                details={"raw_body": response.text[:8000]},
            )
        message = choices[0].get("message") or {}
        content = message.get("content") or ""
        usage_raw = data.get("usage") or {}
        prompt_tokens = float(usage_raw.get("prompt_tokens") or 0)
        completion_tokens = float(usage_raw.get("completion_tokens") or 0)
        return LLMResponse(
            content=str(content),
            model=str(data.get("model") or model),
            finish_reason=str(choices[0].get("finish_reason") or "stop"),
            usage=UsageInfo(
                operation="complete",
                unit_type="tokens",
                units=prompt_tokens + completion_tokens,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                provider=_OPENAI_PROVIDER,
                extra={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "model": model,
                },
            ),
        )


class GeminiLLMProvider(LLMProvider):
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gemini-2.0-flash",
        max_retries: int = 3,
        default_timeout_seconds: float = 60.0,
    ) -> None:
        key = (api_key or "").strip()
        if not key:
            raise ProviderNotConfiguredError(
                "GEMINI_API_KEY is required for GeminiLLMProvider",
                provider=_GEMINI_PROVIDER,
            )
        self._api_key = key
        self._model = model
        self._max_retries = max_retries
        self._default_timeout = default_timeout_seconds
        self._meta = ProviderMetadata(
            name=_GEMINI_PROVIDER,
            vendor="google",
            capabilities=frozenset({"chat", "structured", "json"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def complete(self, request: LLMRequest) -> LLMResponse:
        started = time.perf_counter()
        model = request.model or self._model
        system_parts = [m.content for m in request.messages if m.role == "system"]
        contents: list[dict[str, Any]] = []
        for message in request.messages:
            if message.role == "system":
                continue
            role = "model" if message.role == "assistant" else "user"
            text = message.content
            if role == "user" and system_parts and not contents:
                text = "\n\n".join(system_parts + [text])
            contents.append({"role": role, "parts": [{"text": text}]})

        generation_config: dict[str, Any] = {
            "temperature": request.temperature,
        }
        if request.max_tokens is not None:
            generation_config["maxOutputTokens"] = request.max_tokens
        if request.response_format == "json" or request.json_schema is not None:
            generation_config["responseMimeType"] = "application/json"

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
        )
        response = request_with_retries(
            method="POST",
            url=url,
            provider=_GEMINI_PROVIDER,
            operation="complete",
            timeout_seconds=request.timeout_seconds or self._default_timeout,
            max_retries=self._max_retries,
            params={"key": self._api_key},
            headers={"Content-Type": "application/json"},
            json={"contents": contents, "generationConfig": generation_config},
        )
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderValidationError(
                "Gemini returned non-JSON response",
                provider=_GEMINI_PROVIDER,
                operation="complete",
                details={"raw_body": response.text[:8000]},
            ) from exc

        candidates = data.get("candidates") or []
        if not candidates:
            raise ProviderValidationError(
                "Gemini response missing candidates",
                provider=_GEMINI_PROVIDER,
                operation="complete",
                details={"raw_body": response.text[:8000]},
            )
        parts = ((candidates[0].get("content") or {}).get("parts")) or []
        content = "".join(str(part.get("text") or "") for part in parts if isinstance(part, dict))
        usage_raw = data.get("usageMetadata") or {}
        prompt_tokens = float(usage_raw.get("promptTokenCount") or 0)
        completion_tokens = float(usage_raw.get("candidatesTokenCount") or 0)
        return LLMResponse(
            content=content,
            model=model,
            finish_reason=str(candidates[0].get("finishReason") or "stop"),
            usage=UsageInfo(
                operation="complete",
                unit_type="tokens",
                units=prompt_tokens + completion_tokens,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                provider=_GEMINI_PROVIDER,
                extra={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "model": model,
                },
            ),
        )


def parse_llm_json(content: str) -> dict[str, Any]:
    """Parse JSON object from LLM content; strips optional markdown fences."""
    text = (content or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProviderValidationError(
            f"LLM returned invalid JSON: {exc}",
            provider="llm",
            operation="parse_json",
            details={"raw_content": text[:8000]},
        ) from exc
    if not isinstance(data, dict):
        raise ProviderValidationError(
            "LLM JSON must be an object",
            provider="llm",
            operation="parse_json",
            details={"raw_content": text[:8000]},
        )
    return data
