"""Tests for tiered skill matching."""

from __future__ import annotations

import math

from packages.domain.skill_aliases import skills_match_via_alias
from packages.domain.skill_match import SkillMatchService, cosine_similarity
from packages.providers.embedding import MockEmbeddingProvider


def test_alias_match_javascript_js() -> None:
    assert skills_match_via_alias("JavaScript", "JS")


def test_embedding_synonym_match() -> None:
    matcher = SkillMatchService(MockEmbeddingProvider(), high_threshold=0.85, low_threshold=0.7)
    result = matcher.align(["JavaScript"], ["JS"])
    assert "JavaScript" in result.matched
    assert result.missing == []


def test_true_miss() -> None:
    matcher = SkillMatchService(MockEmbeddingProvider())
    result = matcher.align(["COBOL"], ["Python"])
    assert result.matched == []
    assert "COBOL" in result.missing or "COBOL" in result.possible


def test_possible_weight_scoring() -> None:
    matcher = SkillMatchService(MockEmbeddingProvider())
    from packages.domain.skill_match import SkillMatchResult

    full = SkillMatchResult(matched=["A", "B"], possible=[], missing=[])
    partial = SkillMatchResult(matched=["A"], possible=["B"], missing=[])
    assert matcher.skills_score(full) == 1.0
    assert matcher.skills_score(partial, possible_weight=0.5) == 0.75


def test_cosine_identical_vectors() -> None:
    v = [1.0, 0.0, 0.5]
    assert math.isclose(cosine_similarity(v, v), 1.0)
