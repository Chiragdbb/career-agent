from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from packages.domain.preferences import PreferenceSettings


class PreferencesResponse(BaseModel):
    id: UUID
    user_id: UUID
    status: str
    settings: PreferenceSettings
    created_at: datetime
    updated_at: datetime


class PreferencesUpdateRequest(BaseModel):
    settings: PreferenceSettings


class ParsePreferencesRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    locale_hint: str | None = None


class ParsePreferencesResponse(BaseModel):
    settings: PreferenceSettings
    unparsed_notes: list[str] = []
