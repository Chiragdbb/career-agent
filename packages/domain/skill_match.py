"""Tiered skill matching: alias fast-path then embedding similarity."""

from __future__ import annotations

import math
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

        resume_norm = {normalize_skill(s): s for s in resume_skills if s.strip()}
        resume_canonical = {
            resolve_alias(n) or n: s for n, s in resume_norm.items()
        }

        matched: list[str] = []
        possible: list[str] = []
        missing: list[str] = []
        unresolved_job: list[str] = []
        unresolved_resume: list[str] = []

        for skill in job_skills:
            norm = normalize_skill(skill)
            if not norm:
                continue
            canonical = resolve_alias(norm) or norm
            hit = False
            for r_norm, r_display in resume_norm.items():
                if skills_match_via_alias(skill, r_display):
                    matched.append(skill)
                    hit = True
                    break
            if hit:
                continue
            if canonical in resume_canonical:
                matched.append(skill)
                continue
            unresolved_job.append(skill)

        if not unresolved_job:
            return SkillMatchResult(matched=matched, possible=possible, missing=missing)

        if self._embedding is None:
            missing.extend(unresolved_job)
            return SkillMatchResult(matched=matched, possible=possible, missing=missing)

        for r_display in resume_skills:
            norm = normalize_skill(r_display)
            if norm and resolve_alias(norm) is None and norm not in resume_canonical:
                unresolved_resume.append(r_display)

        if not unresolved_resume:
            missing.extend(unresolved_job)
            return SkillMatchResult(matched=matched, possible=possible, missing=missing)

        texts = unresolved_job + unresolved_resume
        response = self._embedding.embed(EmbeddingRequest(texts=texts, dimensions=64))
        job_vecs = response.embeddings[: len(unresolved_job)]
        resume_vecs = response.embeddings[len(unresolved_job) :]

        for idx, skill in enumerate(unresolved_job):
            best = 0.0
            for r_idx, _ in enumerate(unresolved_resume):
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
