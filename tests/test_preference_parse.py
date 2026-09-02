"""Preference prompt parsing and currency helpers."""

from __future__ import annotations

from packages.domain.llm_tasks import LLMTaskService
from packages.domain.preference_parse import PreferenceParseService
from packages.domain.preference_parse_models import (
    PreferenceParseDraft,
    currency_from_locale,
    merge_parsed_preferences,
)
from packages.domain.preferences import PreferenceSettings, WorkArrangement
from packages.providers.llm import MockLLMProvider


def test_currency_from_locale() -> None:
    assert currency_from_locale("en-IN") == "INR"
    assert currency_from_locale("en_GB") == "GBP"
    assert currency_from_locale(None) == "USD"
    assert currency_from_locale("en-XX") == "USD"


def test_merge_parsed_preferences_applies_salary_currency() -> None:
    draft = PreferenceParseDraft(
        target_roles=["Backend Engineer"],
        minimum_salary=180000,
        salary_currency="USD",
    )
    result = merge_parsed_preferences(draft, locale_currency="INR")
    assert result.settings.target_roles == ["Backend Engineer"]
    assert result.settings.minimum_salary == 180000
    assert result.settings.salary_currency == "USD"


def test_merge_uses_locale_currency_when_salary_without_code() -> None:
    draft = PreferenceParseDraft(minimum_salary=1500000)
    result = merge_parsed_preferences(draft, locale_currency="INR")
    assert result.settings.salary_currency == "INR"


def test_parse_prompt_with_mock_llm() -> None:
    service = PreferenceParseService(LLMTaskService(MockLLMProvider()))
    result = service.parse_prompt(
        "Senior backend engineer remote $180k fintech",
        locale_hint="en-US",
    )
    assert "Backend Engineer" in result.settings.target_roles
    assert "Remote" in result.settings.locations
    assert result.settings.minimum_salary == 180000
    assert result.settings.salary_currency == "USD"


def test_merge_filters_invalid_enums() -> None:
    draft = PreferenceParseDraft(
        work_arrangements=["remote", "invalid"],
        seniority=["senior", "made_up"],
    )
    result = merge_parsed_preferences(draft)
    assert result.settings.work_arrangements == [WorkArrangement.remote]
    assert len(result.settings.seniority) == 1


def test_preference_settings_default_currency() -> None:
    settings = PreferenceSettings()
    assert settings.salary_currency == "USD"
