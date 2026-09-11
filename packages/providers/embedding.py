"""EmbeddingProvider — text embeddings for vector search (pgvector)."""

from __future__ import annotations

import hashlib
import math
import time
from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from packages.providers.base import (
    MockBehavior,
    ProviderMetadata,
    TimeoutMixin,
    UsageInfo,
)
from packages.providers.exceptions import ProviderNotConfiguredError, ProviderValidationError
from packages.providers.http_utils import request_with_retries

DEFAULT_EMBEDDING_DIMENSIONS = 1536
EMBEDDING_CONTENT_VERSION = "v1"


class EmbeddingRequest(TimeoutMixin):
    texts: list[str] = Field(min_length=1)
    model: str | None = None
    dimensions: int = Field(default=DEFAULT_EMBEDDING_DIMENSIONS, ge=8, le=4096)


class EmbeddingResponse(BaseModel):
    embeddings: list[list[float]]
    model: str
    dimensions: int
    usage: UsageInfo


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError

    @abstractmethod
    def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        raise NotImplementedError


def _l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0:
        return vector
    return [x / norm for x in vector]


class MockEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        *,
        model: str = "mock-embedding",
        fail_with: Exception | None = None,
        simulate_timeout: bool = False,
        latency_ms: float = 3.0,
    ) -> None:
        self._model = model
        self._behavior = MockBehavior(
            fail_with=fail_with,
            simulate_timeout=simulate_timeout,
            latency_ms=latency_ms,
            provider_name="mock-embedding",
        )
        self._meta = ProviderMetadata(
            name="mock-embedding",
            vendor="mock",
            capabilities=frozenset({"embed"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        self._behavior.before_call(operation="embed", timeout_seconds=request.timeout_seconds)
        vectors: list[list[float]] = []
        for text in request.texts:
            vectors.append(self._vector_for_text(text, request.dimensions))
        return EmbeddingResponse(
            embeddings=vectors,
            model=request.model or self._model,
            dimensions=request.dimensions,
            usage=self._behavior.usage(
                operation="embed",
                unit_type="tokens",
                units=float(sum(len(t.split()) for t in request.texts) or 1),
            ),
        )

    def _vector_for_text(self, text: str, dimensions: int) -> list[float]:
        normalized = text.strip().lower()
        digest = hashlib.sha256(normalized.encode()).digest()
        base = [((digest[i % len(digest)] / 255.0) * 2 - 1) for i in range(dimensions)]
        # Synonym boost: javascript/js share similar prefix hash bucket
        if normalized in {"js", "javascript", "ecmascript"}:
            base[0] = 0.95
            base[1] = 0.9
        return _l2_normalize(base)


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    """OpenAI / Groq / other OpenAI-compatible `/v1/embeddings` adapter.

    Groq and Gemini do not expose a stable public embeddings API for this project;
    use an OpenAI-compatible endpoint when `OPENAI_API_KEY` (or
    `EMBEDDING_API_KEY`) is set. CI defaults to MockEmbeddingProvider.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "text-embedding-3-small",
        base_url: str = "https://api.openai.com/v1",
        dimensions: int = DEFAULT_EMBEDDING_DIMENSIONS,
        max_retries: int = 3,
        default_timeout_seconds: float = 30.0,
    ) -> None:
        key = (api_key or "").strip()
        if not key:
            raise ProviderNotConfiguredError(
                "EMBEDDING_API_KEY or OPENAI_API_KEY is required",
                provider="openai-compatible-embedding",
            )
        self._api_key = key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._dimensions = dimensions
        self._max_retries = max_retries
        self._default_timeout = default_timeout_seconds
        self._meta = ProviderMetadata(
            name="openai-compatible-embedding",
            vendor="openai-compatible",
            capabilities=frozenset({"embed"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        if not request.texts:
            raise ProviderValidationError(
                "texts must not be empty",
                provider=self._meta.name,
                operation="embed",
            )
        started = time.perf_counter()
        model = request.model or self._model
        dimensions = request.dimensions or self._dimensions
        body = {
            "model": model,
            "input": request.texts,
            "dimensions": dimensions,
        }
        response = request_with_retries(
            method="POST",
            url=f"{self._base_url}/embeddings",
            provider=self._meta.name,
            operation="embed",
            timeout_seconds=request.timeout_seconds or self._default_timeout,
            max_retries=self._max_retries,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        payload = response.json()
        data = payload.get("data") or []
        vectors = [list(item.get("embedding") or []) for item in data]
        if len(vectors) != len(request.texts):
            raise ProviderValidationError(
                "embedding count mismatch",
                provider=self._meta.name,
                operation="embed",
            )
        usage_raw = payload.get("usage") or {}
        tokens = float(usage_raw.get("total_tokens") or sum(len(t.split()) for t in request.texts))
        latency_ms = (time.perf_counter() - started) * 1000.0
        return EmbeddingResponse(
            embeddings=[_l2_normalize(v) for v in vectors],
            model=model,
            dimensions=dimensions,
            usage=UsageInfo(
                operation="embed",
                unit_type="tokens",
                units=tokens,
                latency_ms=latency_ms,
                provider=self._meta.name,
                extra={"request_id": response.headers.get("x-request-id")},
            ),
        )
