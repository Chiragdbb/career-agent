"""Job posting models used by discovery and matching."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ExtractedJob(BaseModel):
    """Validated structured job extracted from untrusted scraped content."""

    title: str = Field(min_length=1)
    company_name: str | None = None
    location: str | None = None
    work_arrangement: str | None = None  # remote | hybrid | on_site
    employment_type: str | None = None
    seniority: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None
    description: str | None = None
    skills: list[str] = Field(default_factory=list)
    url: str
    external_id: str | None = None
    posted_at: str | None = None

    @field_validator("title", "url")
    @classmethod
    def require_non_blank(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise ValueError("must not be blank")
        return cleaned

    @field_validator("skills", mode="before")
    @classmethod
    def normalize_skills(cls, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("skills must be a list")
        out: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
        return out

    @field_validator("salary_min", "salary_max")
    @classmethod
    def non_negative_salary(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("salary must be non-negative")
        return value
