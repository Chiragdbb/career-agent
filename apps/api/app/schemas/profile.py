from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    status: str
    display_name: str | None = None
    headline: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    summary: str | None = None
    created_at: datetime
    updated_at: datetime


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = None
    headline: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    summary: str | None = None

    @field_validator("linkedin_url")
    @classmethod
    def validate_linkedin_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        if not (
            stripped.startswith("http://")
            or stripped.startswith("https://")
            or stripped.startswith("linkedin.com/")
        ):
            raise ValueError(
                "linkedin_url must be an http(s) URL or linkedin.com/ path"
            )
        return stripped

    @field_validator("display_name", "headline", "location", "summary")
    @classmethod
    def validate_text_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        if len(stripped) > 5000:
            raise ValueError("field exceeds maximum length of 5000 characters")
        return stripped
