"""Structured job posting contract for the tiered scrape pipeline.

Scrapers must emit this shape — never raw HTML/DOM — before any LLM call.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


JobSource = Literal["playwright", "firecrawl"]
RemoteType = Literal["remote", "hybrid", "onsite"]
EmploymentType = Literal["full_time", "part_time", "contract", "internship"]


class StructuredJobPosting(BaseModel):
    """Fixed extraction schema (§2.2). The only scrape payload allowed into LLMs."""

    external_job_id: str = Field(min_length=1)
    source: JobSource
    company_name: str = Field(min_length=1)
    company_domain: str | None = None
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    requirements: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    location: str = ""
    remote_type: RemoteType | None = None
    employment_type: EmploymentType | None = None
    seniority: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    application_url: str = Field(min_length=1)
    posted_at: date | None = None
    scraped_at: datetime

    @field_validator(
        "external_job_id",
        "company_name",
        "title",
        "description",
        "application_url",
        "location",
    )
    @classmethod
    def strip_required(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise ValueError("must not be blank")
        return cleaned

    @field_validator("company_domain", mode="before")
    @classmethod
    def normalize_domain(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip().lower()
        text = text.removeprefix("https://").removeprefix("http://")
        text = text.split("/")[0].removeprefix("www.")
        return text or None

    @field_validator("seniority", "salary_currency", mode="before")
    @classmethod
    def blank_optional_str(cls, value: object) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @field_validator("requirements", "skills", mode="before")
    @classmethod
    def normalize_string_list(cls, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("must be a list of strings")
        out: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
        return out

    @field_validator("remote_type", mode="before")
    @classmethod
    def normalize_remote(cls, value: object) -> str | None:
        if value is None or value == "":
            return None
        text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "on_site": "onsite",
            "onsite": "onsite",
            "in_office": "onsite",
            "remote": "remote",
            "hybrid": "hybrid",
        }
        mapped = aliases.get(text, text)
        if mapped not in ("remote", "hybrid", "onsite"):
            return None
        return mapped

    @field_validator("employment_type", mode="before")
    @classmethod
    def normalize_employment(cls, value: object) -> str | None:
        if value is None or value == "":
            return None
        text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "fulltime": "full_time",
            "full_time": "full_time",
            "parttime": "part_time",
            "part_time": "part_time",
            "contract": "contract",
            "contractor": "contract",
            "internship": "internship",
            "intern": "internship",
        }
        mapped = aliases.get(text)
        return mapped

    @model_validator(mode="after")
    def salary_order(self) -> StructuredJobPosting:
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValueError("salary_min must be <= salary_max")
        return self

    def to_llm_payload(self) -> dict[str, Any]:
        """Only schema fields — never HTML/DOM — for downstream LLM calls."""
        return self.model_dump(mode="json")
