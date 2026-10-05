"""Parse schema.org JobPosting JSON-LD from HTML (before LLM extraction)."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from typing import Any

from packages.domain.job_posting import StructuredJobPosting
from packages.domain.job_ingest.text_sanitize import strip_html_to_text

_JOB_POSTING_TYPES = frozenset({"JobPosting", "jobposting"})


def extract_job_posting_json_ld(html: str, *, url: str) -> StructuredJobPosting | None:
    """Return a partial/full StructuredJobPosting when JSON-LD JobPosting is present."""
    if not html or not html.strip():
        return None
    for obj in _iter_job_posting_objects(html):
        posting = _object_to_posting(obj, url=url)
        if posting is not None:
            return posting
    return None


def merge_json_ld_into_posting(
    base: StructuredJobPosting,
    html: str,
) -> StructuredJobPosting:
    """Fill empty fields on an existing posting from JSON-LD."""
    extracted = extract_job_posting_json_ld(html, url=base.application_url)
    if extracted is None:
        return base
    data = base.model_dump()
    other = extracted.model_dump()
    for key, value in other.items():
        if key in ("scraped_at", "source", "external_job_id"):
            continue
        current = data.get(key)
        if current in (None, "", [], 0) and value not in (None, "", []):
            data[key] = value
    if not data.get("skills") and other.get("skills"):
        data["skills"] = other["skills"]
    return StructuredJobPosting.model_validate(data)


def json_ld_gaps(posting: StructuredJobPosting) -> dict[str, Any]:
    """Fields still missing after JSON-LD — safe to send to LLM."""
    gaps: dict[str, Any] = {}
    if not posting.skills:
        gaps["skills"] = []
    if posting.salary_min is None and posting.salary_max is None:
        gaps["salary_min"] = None
        gaps["salary_max"] = None
    if posting.posted_at is None:
        gaps["posted_at"] = None
    if not posting.location:
        gaps["location"] = ""
    if len(posting.description or "") < 80:
        gaps["description"] = posting.description
    return gaps


def _iter_job_posting_objects(html: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for block in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        try:
            parsed = json.loads(block.strip())
        except json.JSONDecodeError:
            continue
        for obj in _flatten_ld(parsed):
            typ = obj.get("@type")
            if isinstance(typ, list):
                types = {str(t).lower() for t in typ}
            else:
                types = {str(typ).lower()} if typ else set()
            if types & _JOB_POSTING_TYPES:
                out.append(obj)
    return out


def _flatten_ld(node: Any) -> list[dict[str, Any]]:
    if isinstance(node, dict):
        if "@graph" in node and isinstance(node["@graph"], list):
            items: list[dict[str, Any]] = []
            for child in node["@graph"]:
                items.extend(_flatten_ld(child))
            return items
        return [node]
    if isinstance(node, list):
        items = []
        for child in node:
            items.extend(_flatten_ld(child))
        return items
    return []


def _object_to_posting(obj: dict[str, Any], *, url: str) -> StructuredJobPosting | None:
    title = _text(obj.get("title"))
    description = _text(obj.get("description"))
    if not title or not description:
        return None

    org = obj.get("hiringOrganization") or {}
    if isinstance(org, list):
        org = org[0] if org else {}
    company_name = _text(org.get("name")) if isinstance(org, dict) else None
    if not company_name:
        company_name = "Unknown Company"

    location = _location_text(obj.get("jobLocation"))
    remote = _remote_type(obj)
    salary_min, salary_max, currency = _salary(obj)
    posted = _posted_date(obj.get("datePosted"))
    skills = _skills(obj)
    domain = None
    if isinstance(org, dict):
        same_as = org.get("sameAs") or org.get("url")
        if isinstance(same_as, str) and "://" in same_as:
            from urllib.parse import urlparse

            domain = (urlparse(same_as).hostname or "").lower().removeprefix("www.")

    external_id = _text(obj.get("identifier")) or url.rstrip("/").split("/")[-1] or url

    try:
        return StructuredJobPosting(
            external_job_id=str(external_id)[:120],
            source="json_ld",
            company_name=company_name,
            company_domain=domain,
            title=title,
            description=description,
            requirements=[],
            skills=skills,
            location=location or "",
            remote_type=remote,
            employment_type=None,
            seniority=_text(obj.get("experienceRequirements")) or _text(obj.get("occupationalCategory")),
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=currency,
            application_url=url,
            posted_at=posted,
            scraped_at=datetime.now(timezone.utc),
        )
    except Exception:
        return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return _text(value.get("name") or value.get("@value"))
    cleaned = str(value).strip()
    if not cleaned:
        return None
    if "<" in cleaned and ">" in cleaned:
        cleaned = strip_html_to_text(cleaned)
    return cleaned or None


def _location_text(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, list):
        parts = [_location_text(item) for item in raw]
        return "; ".join(p for p in parts if p)
    if isinstance(raw, dict):
        addr = raw.get("address")
        if isinstance(addr, dict):
            bits = [addr.get("addressLocality"), addr.get("addressRegion"), addr.get("addressCountry")]
            return ", ".join(str(b).strip() for b in bits if b)
        return _text(raw.get("name")) or ""
    return ""


def _remote_type(obj: dict[str, Any]) -> str | None:
    raw = obj.get("jobLocationType") or obj.get("workplaceType")
    text = (_text(raw) or "").lower()
    if "telecommute" in text or "remote" in text:
        return "remote"
    if "hybrid" in text:
        return "hybrid"
    return None


def _salary(obj: dict[str, Any]) -> tuple[float | None, float | None, str | None]:
    base = obj.get("baseSalary") or obj.get("estimatedSalary")
    if isinstance(base, list):
        base = base[0] if base else None
    if not isinstance(base, dict):
        return None, None, None
    currency = _text(base.get("currency"))
    val = base.get("value")
    if isinstance(val, dict):
        lo = val.get("minValue") or val.get("value")
        hi = val.get("maxValue") or val.get("value")
        try:
            return (
                float(lo) if lo is not None else None,
                float(hi) if hi is not None else None,
                currency,
            )
        except (TypeError, ValueError):
            return None, None, currency
    try:
        num = float(val)
        return num, num, currency
    except (TypeError, ValueError):
        return None, None, currency


def _posted_date(raw: Any) -> date | None:
    text = _text(raw)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _skills(obj: dict[str, Any]) -> list[str]:
    skills: list[str] = []
    for key in ("skills", "qualifications"):
        raw = obj.get(key)
        if isinstance(raw, str):
            skills.extend(s.strip() for s in raw.split(",") if s.strip())
        elif isinstance(raw, list):
            for item in raw:
                t = _text(item)
                if t:
                    skills.append(t)
    return skills[:50]
