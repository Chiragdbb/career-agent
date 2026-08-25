from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

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
