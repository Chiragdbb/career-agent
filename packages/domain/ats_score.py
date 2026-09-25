"""AtsScoreService — JD / preference keyword coverage score (0–100).

Never invents resume content. Only measures overlap between resume text and
target keywords extracted from a job description or preference targets.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "to",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "as",
        "is",
        "are",
        "be",
        "this",
        "that",
        "it",
        "we",
        "you",
        "our",
        "your",
        "will",
        "can",
        "may",
        "must",
        "should",
        "has",
        "have",
        "had",
        "been",
        "being",
        "into",
        "about",
        "over",
        "under",
        "than",
        "then",
        "also",
        "such",
        "using",
        "use",
        "used",
        "via",
        "per",
        "any",
        "all",
        "not",
        "no",
        "yes",
        "etc",
        "including",
        "include",
        "includes",
        "role",
        "job",
        "work",
        "team",
        "company",
        "experience",
        "years",
        "year",
        "required",
        "requirements",
        "preferred",
        "plus",
        "ability",
        "strong",
        "good",
        "excellent",
        "responsible",
        "responsibilities",
        "looking",
        "seek",
        "seeking",
    }
)

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+.#-]{1,}", re.IGNORECASE)


@dataclass
class AtsScoreResult:
    score: int
    matched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


def _tokenize(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for match in _TOKEN_RE.finditer(text or ""):
        token = match.group(0).lower().strip(".-+")
        if len(token) < 3 or token in _STOPWORDS:
            continue
        if token in seen:
            continue
        seen.add(token)
        found.append(token)
    return found


class AtsScoreService:
    """Score resume text against job or preference keyword targets."""

    def score_text(self, resume_text: str, job_text: str) -> AtsScoreResult:
        keywords = _tokenize(job_text)
        return self._score(resume_text, keywords)

    def score_against_preferences(
        self,
        resume_text: str,
        *,
        target_roles: list[str] | None = None,
        skills: list[str] | None = None,
    ) -> AtsScoreResult:
        blob = " ".join([*(target_roles or []), *(skills or [])])
        keywords = _tokenize(blob)
        # Prefer explicit skills list order when provided.
        if skills:
            extra = [s.strip().lower() for s in skills if s and len(s.strip()) >= 2]
            for s in extra:
                if s not in keywords:
                    keywords.append(s)
        return self._score(resume_text, keywords)

    def _score(self, resume_text: str, keywords: list[str]) -> AtsScoreResult:
        if not keywords:
            return AtsScoreResult(score=0, matched=[], missing=[], keywords=[])
        resume_tokens = set(_tokenize(resume_text))
        # Also allow substring match for multi-word-ish tokens already split.
        resume_lower = (resume_text or "").lower()
        matched: list[str] = []
        missing: list[str] = []
        for kw in keywords:
            if kw in resume_tokens or kw in resume_lower:
                matched.append(kw)
            else:
                missing.append(kw)
        score = int(round(100 * len(matched) / len(keywords)))
        score = max(0, min(100, score))
        return AtsScoreResult(
            score=score,
            matched=matched,
            missing=missing,
            keywords=list(keywords),
        )
