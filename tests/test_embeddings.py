"""Tests for embedding provider, hybrid scoring, and similarity helpers."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from packages.domain.job_match import (
    SCORING_ALGORITHM_VERSION,
    JobMatchService,
)
from packages.domain.preferences import PreferenceSettings as Prefs
from packages.domain.skill_match import cosine_similarity
from packages.providers.embedding import EmbeddingRequest, MockEmbeddingProvider


def test_mock_embedding_deterministic_and_normalized() -> None:
    provider = MockEmbeddingProvider()
    a = provider.embed(EmbeddingRequest(texts=["python engineer"], dimensions=32))
    b = provider.embed(EmbeddingRequest(texts=["python engineer"], dimensions=32))
    assert a.embeddings[0] == b.embeddings[0]
    norm = sum(x * x for x in a.embeddings[0]) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_hybrid_scoring_preserves_deterministic_core() -> None:
    session = MagicMock()
    service = JobMatchService(session, uuid.uuid4(), embedding=MockEmbeddingProvider())
    job = MagicMock()
    job.title = "Senior Python Engineer"
    job.description = "Build APIs"
    job.details = {
        "location": "remote",
        "work_arrangement": "remote",
        "skills": ["python"],
        "seniority": "senior",
        "salary_max": 180000,
        "currency": "USD",
    }
    job.embedding = None
    prefs = Prefs(
        target_roles=["Python Engineer"],
        locations=["remote"],
        work_arrangements=[],
        minimum_salary=100000,
        seniority=[],
    )
    breakdown = service.score_job(job, prefs, resume_skills=["python"])
    assert breakdown.algorithm_version == SCORING_ALGORITHM_VERSION
    assert breakdown.deterministic_total > 0
    assert 0.0 <= breakdown.semantic <= 1.0
    # Missing embeddings → neutral semantic; total close to deterministic blend
    expected = breakdown.deterministic_total * 0.85 + 0.5 * 0.15
    assert abs(breakdown.total - expected) < 0.02


def test_cosine_similarity_identical() -> None:
    v = [0.1, 0.2, 0.3]
    assert cosine_similarity(v, v) > 0.99
