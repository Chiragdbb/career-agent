"""Profile and preferences CRUD tests."""

from __future__ import annotations

import uuid

import pytest

from database.models.schema import User, UserPreference, UserProfile


def _ensure_user_a(auth_client) -> str:
    response = auth_client.get(
        "/api/v1/me",
        headers={"Authorization": "Bearer token-user-a"},
    )
    assert response.status_code == 200
    return response.json()["id"]


def _ensure_user_b(auth_client) -> str:
    response = auth_client.get(
        "/api/v1/me",
        headers={"Authorization": "Bearer token-user-b"},
    )
    assert response.status_code == 200
    return response.json()["id"]


def _cleanup_profile_preferences(session, user_ids: list[uuid.UUID]) -> None:
    for user_id in user_ids:
        session.query(UserProfile).filter(UserProfile.user_id == user_id).delete()
        session.query(UserPreference).filter(UserPreference.user_id == user_id).delete()
    session.commit()


@pytest.fixture
def profile_preferences_cleanup(auth_client):
    from app.database import get_session_factory

    user_a_id = uuid.UUID(_ensure_user_a(auth_client))
    user_b_id = uuid.UUID(_ensure_user_b(auth_client))

    session = get_session_factory()()
    try:
        _cleanup_profile_preferences(session, [user_a_id, user_b_id])
        yield {"user_a": user_a_id, "user_b": user_b_id}
    finally:
        _cleanup_profile_preferences(session, [user_a_id, user_b_id])
        session.close()


def test_unauthenticated_profile_rejected(auth_client) -> None:
    response = auth_client.get("/api/v1/profile")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_unauthenticated_preferences_rejected(auth_client) -> None:
    response = auth_client.get("/api/v1/preferences")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_profile_crud(auth_client, profile_preferences_cleanup) -> None:
    user_a_id = profile_preferences_cleanup["user_a"]

    get_empty = auth_client.get(
        "/api/v1/profile",
        headers={"Authorization": "Bearer token-user-a"},
    )
    assert get_empty.status_code == 200
    body = get_empty.json()
    assert body["user_id"] == str(user_a_id)
    assert body["display_name"] is None

    update = auth_client.put(
        "/api/v1/profile",
        headers={"Authorization": "Bearer token-user-a"},
        json={
            "display_name": "Alex Candidate",
            "headline": "Software Engineer",
            "location": "San Francisco, CA",
            "linkedin_url": "https://linkedin.com/in/alex",
            "summary": "Building reliable systems.",
        },
    )
    assert update.status_code == 200
    updated = update.json()
    assert updated["display_name"] == "Alex Candidate"
    assert updated["headline"] == "Software Engineer"
    assert updated["linkedin_url"] == "https://linkedin.com/in/alex"

    again = auth_client.get(
        "/api/v1/profile",
        headers={"Authorization": "Bearer token-user-a"},
    )
    assert again.status_code == 200
    assert again.json()["display_name"] == "Alex Candidate"


def test_profile_validation_rejects_bad_linkedin(auth_client, profile_preferences_cleanup) -> None:
    response = auth_client.put(
        "/api/v1/profile",
        headers={"Authorization": "Bearer token-user-a"},
        json={"linkedin_url": "not-a-valid-url"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_preferences_crud_and_validation(auth_client, profile_preferences_cleanup) -> None:
    user_a_id = profile_preferences_cleanup["user_a"]

    get_defaults = auth_client.get(
        "/api/v1/preferences",
        headers={"Authorization": "Bearer token-user-a"},
    )
    assert get_defaults.status_code == 200
    defaults = get_defaults.json()
    assert defaults["user_id"] == str(user_a_id)
    assert defaults["settings"]["target_roles"] == []
    assert defaults["settings"]["job_freshness"] == "last_7d"
    assert defaults["settings"]["daily_application_limit"] == 5

    payload = {
        "settings": {
            "target_roles": ["Backend Engineer", "Platform Engineer"],
            "locations": ["Remote", "New York, NY"],
            "work_arrangements": ["remote", "hybrid"],
            "minimum_salary": 150000,
            "salary_currency": "USD",
            "seniority": ["senior", "staff"],
            "industries": ["Fintech", "SaaS"],
            "company_sizes": ["startup", "medium"],
            "employment_types": ["full_time", "contract"],
            "job_freshness": "last_3d",
            "application_automation_mode": "assisted",
            "outreach_approval_mode": "always_approve",
            "daily_application_limit": 8,
            "daily_outreach_limit": 15,
        }
    }
    update = auth_client.put(
        "/api/v1/preferences",
        headers={"Authorization": "Bearer token-user-a"},
        json=payload,
    )
    assert update.status_code == 200
    saved = update.json()["settings"]
    assert saved["target_roles"] == ["Backend Engineer", "Platform Engineer"]
    assert saved["minimum_salary"] == 150000
    assert saved["salary_currency"] == "USD"
    assert saved["work_arrangements"] == ["remote", "hybrid"]

    invalid = auth_client.put(
        "/api/v1/preferences",
        headers={"Authorization": "Bearer token-user-a"},
        json={"settings": {"daily_application_limit": -1}},
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"


def test_users_cannot_see_each_others_profile_or_preferences(
    auth_client, profile_preferences_cleanup
) -> None:
    auth_client.put(
        "/api/v1/profile",
        headers={"Authorization": "Bearer token-user-a"},
        json={"display_name": "User A Only"},
    )
    auth_client.put(
        "/api/v1/profile",
        headers={"Authorization": "Bearer token-user-b"},
        json={"display_name": "User B Only"},
    )
    auth_client.put(
        "/api/v1/preferences",
        headers={"Authorization": "Bearer token-user-a"},
        json={"settings": {"target_roles": ["Role A"], "daily_application_limit": 3}},
    )
    auth_client.put(
        "/api/v1/preferences",
        headers={"Authorization": "Bearer token-user-b"},
        json={"settings": {"target_roles": ["Role B"], "daily_application_limit": 9}},
    )

    profile_a = auth_client.get(
        "/api/v1/profile",
        headers={"Authorization": "Bearer token-user-a"},
    ).json()
    profile_b = auth_client.get(
        "/api/v1/profile",
        headers={"Authorization": "Bearer token-user-b"},
    ).json()
    assert profile_a["display_name"] == "User A Only"
    assert profile_b["display_name"] == "User B Only"
    assert profile_a["user_id"] != profile_b["user_id"]

    prefs_a = auth_client.get(
        "/api/v1/preferences",
        headers={"Authorization": "Bearer token-user-a"},
    ).json()["settings"]
    prefs_b = auth_client.get(
        "/api/v1/preferences",
        headers={"Authorization": "Bearer token-user-b"},
    ).json()["settings"]
    assert prefs_a["target_roles"] == ["Role A"]
    assert prefs_b["target_roles"] == ["Role B"]
    assert prefs_a["daily_application_limit"] == 3
    assert prefs_b["daily_application_limit"] == 9


def test_parse_preferences_prompt(auth_client, profile_preferences_cleanup) -> None:
    from packages.domain.llm_tasks import LLMTaskService
    from packages.providers.llm import MockLLMProvider

    auth_client.app.state.llm_task_service = LLMTaskService(MockLLMProvider())

    response = auth_client.post(
        "/api/v1/preferences/parse-prompt",
        headers={"Authorization": "Bearer token-user-a"},
        json={
            "prompt": "Senior backend engineer remote in NYC $180k",
            "locale_hint": "en-US",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "Backend Engineer" in body["settings"]["target_roles"]
    assert body["settings"]["minimum_salary"] == 180000
    assert body["settings"]["salary_currency"] == "USD"


def test_parse_preferences_prompt_requires_auth(auth_client) -> None:
    response = auth_client.post(
        "/api/v1/preferences/parse-prompt",
        json={"prompt": "Engineer roles"},
    )
    assert response.status_code == 401
