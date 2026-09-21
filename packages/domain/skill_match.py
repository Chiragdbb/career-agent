"""Tiered skill matching: alias fast-path, fuzzy containment, then embedding similarity."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from packages.domain.skill_aliases import normalize_skill, resolve_alias, skills_match_via_alias
from packages.providers.embedding import EmbeddingProvider, EmbeddingRequest


@dataclass(frozen=True)
class SkillMatchResult:
    matched: list[str]
    possible: list[str]
    missing: list[str]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def skills_match_fuzzy(job_skill: str, resume_skill: str) -> bool:
    """Match when wording differs but one skill contains the other as a token/phrase."""
    if skills_match_via_alias(job_skill, resume_skill):
        return True
    a = normalize_skill(job_skill)
    b = normalize_skill(resume_skill)
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if len(shorter) >= 3 and (
        longer == shorter
        or longer.startswith(shorter + " ")
        or longer.endswith(" " + shorter)
        or f" {shorter} " in f" {longer} "
        or longer.startswith(shorter + ".")
        or longer.endswith("." + shorter)
    ):
        return True
    a_tokens = {t for t in re.split(r"[\s/.]+", a) if len(t) >= 2}
    b_tokens = {t for t in re.split(r"[\s/.]+", b) if len(t) >= 2}
    if not a_tokens or not b_tokens:
        return False
    if a_tokens <= b_tokens or b_tokens <= a_tokens:
        return True
    ca = resolve_alias(a) or a
    cb = resolve_alias(b) or b
    return ca == cb


class SkillMatchService:
    def __init__(
        self,
        embedding: EmbeddingProvider | None = None,
        *,
        high_threshold: float = 0.85,
        low_threshold: float = 0.7,
    ) -> None:
        self._embedding = embedding
        self._high = high_threshold
        self._low = low_threshold

    def align(self, job_skills: list[str], resume_skills: list[str]) -> SkillMatchResult:
        if not job_skills:
            return SkillMatchResult(matched=[], possible=[], missing=[])

        resume_clean = [s for s in resume_skills if s and str(s).strip()]
        matched: list[str] = []
        possible: list[str] = []
        missing: list[str] = []
        unresolved_job: list[str] = []

        for skill in job_skills:
            if not str(skill).strip():
                continue
            hit = any(skills_match_fuzzy(skill, r) for r in resume_clean)
            if hit:
                matched.append(skill)
            else:
                unresolved_job.append(skill)

        if not unresolved_job:
            return SkillMatchResult(matched=matched, possible=possible, missing=missing)

        if self._embedding is None or not resume_clean:
            missing.extend(unresolved_job)
            return SkillMatchResult(matched=matched, possible=possible, missing=missing)

        texts = unresolved_job + resume_clean
        response = self._embedding.embed(EmbeddingRequest(texts=texts, dimensions=64))
        job_vecs = response.embeddings[: len(unresolved_job)]
        resume_vecs = response.embeddings[len(unresolved_job) :]

        for idx, skill in enumerate(unresolved_job):
            best = 0.0
            for r_idx, _ in enumerate(resume_clean):
                sim = cosine_similarity(job_vecs[idx], resume_vecs[r_idx])
                best = max(best, sim)
            if best >= self._high:
                matched.append(skill)
            elif best >= self._low:
                possible.append(skill)
            else:
                missing.append(skill)

        return SkillMatchResult(matched=matched, possible=possible, missing=missing)

    def skills_score(
        self,
        result: SkillMatchResult,
        *,
        possible_weight: float = 0.5,
    ) -> float:
        total = len(result.matched) + len(result.possible) + len(result.missing)
        if total == 0:
            return 0.5
        points = len(result.matched) + len(result.possible) * possible_weight
        return points / total
