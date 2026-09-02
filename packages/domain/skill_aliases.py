"""Common technology and role skill synonym groups."""

from __future__ import annotations

import re

# canonical -> aliases (all lowercase)
_SKILL_GROUPS: dict[str, list[str]] = {
    "javascript": ["js", "ecmascript", "node.js", "nodejs"],
    "typescript": ["ts"],
    "python": ["py"],
    "google cloud platform": ["gcp", "google cloud"],
    "amazon web services": ["aws"],
    "microsoft azure": ["azure"],
    "kubernetes": ["k8s"],
    "postgresql": ["postgres", "psql"],
    "react": ["reactjs", "react.js"],
    "machine learning": ["ml"],
    "artificial intelligence": ["ai"],
    "continuous integration": ["ci"],
    "continuous delivery": ["cd"],
    "ci/cd": ["cicd", "ci cd"],
}

_ALIAS_TO_CANONICAL: dict[str, str] = {}
for canonical, aliases in _SKILL_GROUPS.items():
    _ALIAS_TO_CANONICAL[canonical] = canonical
    for alias in aliases:
        _ALIAS_TO_CANONICAL[alias] = canonical


def normalize_skill(skill: str) -> str:
    text = skill.strip().lower()
    text = re.sub(r"[^\w\s/+.-]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def resolve_alias(skill: str) -> str | None:
    normalized = normalize_skill(skill)
    if not normalized:
        return None
    return _ALIAS_TO_CANONICAL.get(normalized)


def skills_match_via_alias(a: str, b: str) -> bool:
    na = normalize_skill(a)
    nb = normalize_skill(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    ca = resolve_alias(na) or na
    cb = resolve_alias(nb) or nb
    return ca == cb
