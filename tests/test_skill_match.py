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


def test_fuzzy_match_python_experience_wording() -> None:
    from packages.domain.skill_match import skills_match_fuzzy

    assert skills_match_fuzzy("Python", "Python 3")
    assert skills_match_fuzzy("React", "React.js")
    assert skills_match_fuzzy("PostgreSQL", "Postgres")


def test_find_known_skills_in_resume_text() -> None:
    from packages.domain.skill_aliases import find_known_skills_in_text

    found = find_known_skills_in_text(
        "Built APIs with FastAPI and deployed to AWS using Docker and Kubernetes."
    )
    lowered = {s.lower() for s in found}
    assert "fastapi" in lowered or any("fastapi" in s.lower() for s in found)
    assert any("aws" in s.lower() or "amazon" in s.lower() for s in found)
    assert any("docker" in s.lower() for s in found)
    assert any("kubernetes" in s.lower() or "k8s" in s.lower() for s in found)
