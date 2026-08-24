"""LLMProvider — chat / structured generation.

Product default target (not implemented here): Groq or Gemini.
Do not add OpenAI adapters in this step.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from packages.providers.base import (
    MockBehavior,
    ProviderMetadata,
    TimeoutMixin,
    UsageInfo,
)


class LLMMessage(BaseModel):
    role: str
    content: str


class LLMRequest(TimeoutMixin):
    messages: list[LLMMessage] = Field(min_length=1)
    model: str | None = None
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=1024, ge=1)
    response_format: str | None = None  # e.g. "json" | "text"
    json_schema: dict[str, Any] | None = None


class LLMResponse(BaseModel):
    content: str
    model: str
    finish_reason: str = "stop"
    usage: UsageInfo


class LLMProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError

    @abstractmethod
    def complete(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError


class MockLLMProvider(LLMProvider):
    def __init__(
        self,
        *,
        content: str = '{"ok": true}',
        model: str = "mock-llm",
        fail_with: Exception | None = None,
        simulate_timeout: bool = False,
        latency_ms: float = 10.0,
        prompt_tokens: float = 10.0,
        completion_tokens: float = 5.0,
    ) -> None:
        self._content = content
        self._model = model
        self._prompt_tokens = prompt_tokens
        self._completion_tokens = completion_tokens
        self._behavior = MockBehavior(
            fail_with=fail_with,
            simulate_timeout=simulate_timeout,
            latency_ms=latency_ms,
            provider_name="mock-llm",
        )
        self._meta = ProviderMetadata(
            name="mock-llm",
            vendor="mock",
            capabilities=frozenset({"chat", "structured"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def complete(self, request: LLMRequest) -> LLMResponse:
        self._behavior.before_call(operation="complete", timeout_seconds=request.timeout_seconds)
        total = self._prompt_tokens + self._completion_tokens
        return LLMResponse(
            content=self._content,
            model=request.model or self._model,
            usage=self._behavior.usage(
                operation="complete",
                unit_type="tokens",
                units=total,
                extra={
                    "prompt_tokens": self._prompt_tokens,
                    "completion_tokens": self._completion_tokens,
                },
            ),
        )
