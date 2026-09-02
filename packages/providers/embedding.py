"""EmbeddingProvider — text embeddings for vector search (pgvector)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from packages.providers.base import (
    MockBehavior,
    ProviderMetadata,
    TimeoutMixin,
    UsageInfo,
)


class EmbeddingRequest(TimeoutMixin):
    texts: list[str] = Field(min_length=1)
    model: str | None = None
    dimensions: int = Field(default=1536, ge=8, le=4096)


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
        import hashlib

        normalized = text.strip().lower()
        digest = hashlib.sha256(normalized.encode()).digest()
        base = [((digest[i % len(digest)] / 255.0) * 2 - 1) for i in range(dimensions)]
        # Synonym boost: javascript/js share similar prefix hash bucket
        if normalized in {"js", "javascript", "ecmascript"}:
            base[0] = 0.95
            base[1] = 0.9
        return base
