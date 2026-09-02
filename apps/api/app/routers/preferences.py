from __future__ import annotations

from fastapi import APIRouter

from app.dependencies import CurrentUserIdDep, DbSessionDep, LlmTaskServiceDep
from app.schemas.preferences import (
    ParsePreferencesRequest,
    ParsePreferencesResponse,
    PreferencesResponse,
    PreferencesUpdateRequest,
)
from packages.domain.preference_parse import PreferenceParseService
from packages.domain.preferences import PreferencesService

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("", response_model=PreferencesResponse)
def get_preferences(
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> PreferencesResponse:
    service = PreferencesService(session, user_id)
    row = service.get_or_create()
    return PreferencesResponse(
        id=row.id,
        user_id=row.user_id,
        status=row.status.value if hasattr(row.status, "value") else str(row.status),
        settings=service.get_settings(),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.put("", response_model=PreferencesResponse)
def update_preferences(
    body: PreferencesUpdateRequest,
    session: DbSessionDep,
    user_id: CurrentUserIdDep,
) -> PreferencesResponse:
    service = PreferencesService(session, user_id)
    row = service.update(body.settings)
    return PreferencesResponse(
        id=row.id,
        user_id=row.user_id,
        status=row.status.value if hasattr(row.status, "value") else str(row.status),
        settings=body.settings,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.post("/parse-prompt", response_model=ParsePreferencesResponse)
def parse_preferences_prompt(
    body: ParsePreferencesRequest,
    llm_tasks: LlmTaskServiceDep,
    _user_id: CurrentUserIdDep,
) -> ParsePreferencesResponse:
    result = PreferenceParseService(llm_tasks).parse_prompt(
        body.prompt.strip(),
        locale_hint=body.locale_hint,
    )
    return ParsePreferencesResponse(
        settings=result.settings,
        unparsed_notes=result.unparsed_notes,
    )
