"""Deterministic/heuristic resume parsing from extracted plain text.

Does not call LLMs. Only surfaces values found in the source text —
never fabricates experience, skills, dates, employers, achievements, or metrics.
"""

from __future__ import annotations

import re

from packages.domain.resume_models import (
    PARSER_VERSION,
    CertificationEntry,
    ContactInfo,
    EducationEntry,
    ExperienceEntry,
    ProjectEntry,
    StructuredResume,
)

_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)
_PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s\-.]?)?(?:\(?\d{2,4}\)?[\s\-.]?)?\d{3}[\s\-.]?\d{4}\b"
)
_LINKEDIN_RE = re.compile(
    r"https?://(?:www\.)?linkedin\.com/in/[A-Za-z0-9\-_%/]+",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_DATE_RANGE_RE = re.compile(
    r"(?P<start>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\d{4})"
    r"\s*[-–—to]+\s*"
    r"(?P<end>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\d{4}|Present|Current)",
    re.IGNORECASE,
)

_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "summary": ("summary", "professional summary", "profile", "objective", "about"),
    "experience": (
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "work history",
    ),
    "projects": ("projects", "personal projects", "selected projects"),
    "education": ("education", "academic background", "academics"),
    "skills": (
        "skills",
        "technical skills",
        "technologies",
        "tech stack",
        "core competencies",
    ),
    "certifications": (
        "certifications",
        "certificates",
        "licenses",
        "licenses & certifications",
    ),
}

_HEADER_LOOKUP: dict[str, str] = {}
for _canonical, _aliases in _SECTION_ALIASES.items():
    for _alias in _aliases:
        _HEADER_LOOKUP[_alias] = _canonical


def parse_structured_resume(plain_text: str) -> StructuredResume:
    """Parse plain text into a StructuredResume using section heuristics only."""
    text = (plain_text or "").strip()
    if not text:
        return StructuredResume(parser_version=PARSER_VERSION)

    lines = [_normalize_line(line) for line in text.splitlines()]
    lines = [line for line in lines if line]

    contact = _extract_contact(lines, text)
    sections = _split_sections(lines)

    summary = _join_block(sections.get("summary", [])) or None
    experience = _parse_experience(sections.get("experience", []))
    projects = _parse_projects(sections.get("projects", []))
    education = _parse_education(sections.get("education", []))
    skills = _parse_skills(sections.get("skills", []))
    certifications = _parse_certifications(sections.get("certifications", []))

    return StructuredResume(
        contact=contact,
        summary=summary,
        experience=experience,
        projects=projects,
        education=education,
        skills=skills,
        certifications=certifications,
        parser_version=PARSER_VERSION,
    )


def _normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", (line or "").strip())


def _extract_contact(lines: list[str], full_text: str) -> ContactInfo:
    email_match = _EMAIL_RE.search(full_text)
    phone_match = _PHONE_RE.search(full_text)
    linkedin_match = _LINKEDIN_RE.search(full_text)

    website: str | None = None
    for match in _URL_RE.finditer(full_text):
        url = match.group(0).rstrip(".,);]")
        if "linkedin.com" in url.lower():
            continue
        website = url
        break

    full_name: str | None = None
    for line in lines[:8]:
        if _is_section_header(line):
            break
        if _EMAIL_RE.search(line) or _PHONE_RE.search(line) or _URL_RE.search(line):
            continue
        if len(line.split()) <= 6 and not line.endswith(":"):
            full_name = line
            break

    location: str | None = None
    for line in lines[:12]:
        if _is_section_header(line):
            break
        lower = line.lower()
        if any(token in lower for token in (",", "remote")) and not _EMAIL_RE.search(line):
            if _PHONE_RE.search(line) or _URL_RE.search(line):
                continue
            if full_name and line == full_name:
                continue
            # Prefer short location-like lines.
            if len(line) <= 80:
                location = line
                break

    return ContactInfo(
        full_name=full_name,
        email=email_match.group(0) if email_match else None,
        phone=phone_match.group(0).strip() if phone_match else None,
        location=location,
        linkedin_url=linkedin_match.group(0).rstrip("/") if linkedin_match else None,
        website_url=website,
    )


def _is_section_header(line: str) -> bool:
    cleaned = line.strip().rstrip(":").strip().lower()
    return cleaned in _HEADER_LOOKUP


def _section_key(line: str) -> str | None:
    cleaned = line.strip().rstrip(":").strip().lower()
    return _HEADER_LOOKUP.get(cleaned)


def _split_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        key = _section_key(line)
        if key is not None:
            current = key
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)
    return sections


def _join_block(lines: list[str]) -> str:
    return "\n".join(lines).strip()


def _parse_experience(lines: list[str]) -> list[ExperienceEntry]:
    blocks = _split_entry_blocks(lines)
    entries: list[ExperienceEntry] = []
    for block in blocks:
        if not block:
            continue
        header = block[0]
        date_match = _DATE_RANGE_RE.search(header)
        start_date = date_match.group("start") if date_match else None
        end_raw = date_match.group("end") if date_match else None
        is_current = bool(end_raw and end_raw.lower() in {"present", "current"})
        end_date = None if is_current else end_raw

        title: str | None = None
        company: str | None = None
        location: str | None = None

        header_wo_dates = _DATE_RANGE_RE.sub("", header).strip(" |-–—,")
        if " at " in header_wo_dates.lower():
            parts = re.split(r"\s+at\s+", header_wo_dates, maxsplit=1, flags=re.IGNORECASE)
            title = parts[0].strip() or None
            company = parts[1].strip() or None if len(parts) > 1 else None
        elif " | " in header_wo_dates:
            parts = [p.strip() for p in header_wo_dates.split("|")]
            title = parts[0] or None
            company = parts[1] if len(parts) > 1 else None
            location = parts[2] if len(parts) > 2 else None
        elif " — " in header_wo_dates or " - " in header_wo_dates:
            parts = re.split(r"\s+[—\-]\s+", header_wo_dates, maxsplit=1)
            title = parts[0].strip() or None
            company = parts[1].strip() or None if len(parts) > 1 else None
        else:
            title = header_wo_dates or None
            if len(block) > 1 and not block[1].startswith(("•", "-", "*")):
                company = block[1]

        bullets = _collect_bullets(block[1:])
        # If second line was treated as company, exclude it from bullets source.
        if company and len(block) > 1 and block[1] == company:
            bullets = _collect_bullets(block[2:])

        entries.append(
            ExperienceEntry(
                company=company,
                title=title,
                location=location,
                start_date=start_date,
                end_date=end_date,
                is_current=is_current,
                bullets=bullets,
            )
        )
    return entries


def _parse_projects(lines: list[str]) -> list[ProjectEntry]:
    blocks = _split_entry_blocks(lines)
    entries: list[ProjectEntry] = []
    for block in blocks:
        if not block:
            continue
        name = block[0]
        url = None
        url_match = _URL_RE.search(name)
        if url_match:
            url = url_match.group(0).rstrip(".,);]")
            name = _URL_RE.sub("", name).strip(" |-–—")
        bullets = _collect_bullets(block[1:])
        description = None
        if not bullets and len(block) > 1:
            description = " ".join(block[1:])
        entries.append(
            ProjectEntry(
                name=name or None,
                description=description,
                url=url,
                bullets=bullets,
            )
        )
    return entries


def _parse_education(lines: list[str]) -> list[EducationEntry]:
    blocks = _split_entry_blocks(lines)
    entries: list[EducationEntry] = []
    for block in blocks:
        if not block:
            continue
        header = block[0]
        date_match = _DATE_RANGE_RE.search(header)
        start_date = date_match.group("start") if date_match else None
        end_raw = date_match.group("end") if date_match else None
        end_date = None if end_raw and end_raw.lower() in {"present", "current"} else end_raw
        header_wo_dates = _DATE_RANGE_RE.sub("", header).strip(" |-–—,")

        institution: str | None = header_wo_dates or None
        degree: str | None = None
        field_of_study: str | None = None
        if " — " in header_wo_dates or " - " in header_wo_dates:
            parts = re.split(r"\s+[—\-]\s+", header_wo_dates, maxsplit=1)
            institution = parts[0].strip() or None
            degree = parts[1].strip() or None if len(parts) > 1 else None
        elif " | " in header_wo_dates:
            parts = [p.strip() for p in header_wo_dates.split("|")]
            institution = parts[0] or None
            degree = parts[1] if len(parts) > 1 else None
            field_of_study = parts[2] if len(parts) > 2 else None

        details = [line.lstrip("•-* ").strip() for line in block[1:] if line.strip()]
        entries.append(
            EducationEntry(
                institution=institution,
                degree=degree,
                field_of_study=field_of_study,
                start_date=start_date,
                end_date=end_date,
                details=details,
            )
        )
    return entries


def _parse_skills(lines: list[str]) -> list[str]:
    skills: list[str] = []
    for line in lines:
        # Split common skill list delimiters without inventing tokens.
        chunks = re.split(r"[,;|•]", line)
        for chunk in chunks:
            skill = chunk.strip(" -*")
            if skill and skill not in skills:
                skills.append(skill)
    return skills


def _parse_certifications(lines: list[str]) -> list[CertificationEntry]:
    entries: list[CertificationEntry] = []
    for line in lines:
        if not line.strip():
            continue
        name = line
        issuer = None
        date = None
        if " — " in line or " - " in line:
            parts = re.split(r"\s+[—\-]\s+", line, maxsplit=2)
            name = parts[0].strip()
            if len(parts) > 1:
                issuer = parts[1].strip() or None
            if len(parts) > 2:
                date = parts[2].strip() or None
        entries.append(CertificationEntry(name=name or None, issuer=issuer, date=date))
    return entries


def _split_entry_blocks(lines: list[str]) -> list[list[str]]:
    """Split section lines into entry blocks; a new block starts on non-bullet lines."""
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        is_bullet = line.startswith(("•", "-", "*")) or (
            len(line) > 2 and line[0].isdigit() and line[1] in {".", ")"}
        )
        if not is_bullet and current:
            blocks.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append(current)
    return blocks


def _collect_bullets(lines: list[str]) -> list[str]:
    bullets: list[str] = []
    for line in lines:
        cleaned = line.lstrip("•-* ").strip()
        if cleaned:
            bullets.append(cleaned)
    return bullets
