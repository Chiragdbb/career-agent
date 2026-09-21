"""Common technology and role skill synonym groups."""

from __future__ import annotations

import re

# canonical -> aliases (all lowercase)
_SKILL_GROUPS: dict[str, list[str]] = {
    "javascript": ["js", "ecmascript", "node.js", "nodejs", "node"],
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
    "ci/cd": ["cicd", "ci cd", "ci/cd pipelines"],
    "docker": ["containers", "containerization"],
    "fastapi": ["fast api"],
    "django": [],
    "flask": [],
    "sql": ["structured query language"],
    "nosql": [],
    "mongodb": ["mongo"],
    "redis": [],
    "graphql": [],
    "rest": ["restful", "rest api", "rest apis"],
    "java": [],
    "golang": ["go lang"],
    "rust": [],
    "c++": ["cpp"],
    "c#": ["csharp", "c sharp"],
    "next.js": ["nextjs", "next"],
    "vue": ["vue.js", "vuejs"],
    "angular": ["angularjs"],
    "terraform": [],
    "ansible": [],
    "linux": ["unix"],
    "git": ["github", "gitlab"],
}

_ALIAS_TO_CANONICAL: dict[str, str] = {}
for canonical, aliases in _SKILL_GROUPS.items():
    _ALIAS_TO_CANONICAL[canonical] = canonical
    for alias in aliases:
        _ALIAS_TO_CANONICAL[alias] = canonical

# Short tokens that need word-boundary matching only (avoid false positives).
_SHORT_ALIAS_MIN_BOUNDARY = frozenset(
    {"js", "ts", "py", "ml", "ai", "ci", "cd", "go", "k8s", "aws", "gcp"}
)


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


def known_skill_terms() -> list[str]:
    """All known skill phrases (canonical + aliases), longest first for scanning."""
    terms = list(_ALIAS_TO_CANONICAL.keys())
    terms.sort(key=len, reverse=True)
    return terms


def find_known_skills_in_text(text: str) -> list[str]:
    """Return display forms of known skills found in free text (from resume body)."""
    if not text or not text.strip():
        return []
    lowered = text.lower()
    found: list[str] = []
    seen: set[str] = set()
    for term in known_skill_terms():
        canonical = _ALIAS_TO_CANONICAL[term]
        if canonical in seen:
            continue
        if term in _SHORT_ALIAS_MIN_BOUNDARY or len(term) <= 2:
            pattern = rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])"
            if not re.search(pattern, lowered):
                continue
        elif term not in lowered:
            continue
        seen.add(canonical)
        found.append(_display_skill(canonical))
    return found


def _display_skill(canonical: str) -> str:
    special = {
        "javascript": "JavaScript",
        "typescript": "TypeScript",
        "postgresql": "PostgreSQL",
        "mongodb": "MongoDB",
        "graphql": "GraphQL",
        "ci/cd": "CI/CD",
        "next.js": "Next.js",
        "node.js": "Node.js",
        "c++": "C++",
        "c#": "C#",
        "aws": "AWS",
        "gcp": "GCP",
        "fastapi": "FastAPI",
    }
    if canonical in special:
        return special[canonical]
    return " ".join(part.capitalize() for part in canonical.split())
