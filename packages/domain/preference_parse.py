"""Parse free-text job-search prompts into structured preferences via LLM."""

from __future__ import annotations

from typing import TYPE_CHECKING

from packages.domain.preference_parse_models import (
    ParsedPreferencesResult,
    currency_from_locale,
    merge_parsed_preferences,
)

if TYPE_CHECKING:
    from packages.domain.llm_tasks import LLMTaskService


class PreferenceParseService:
    """Turn a natural-language prompt into structured preference settings."""

    def __init__(self, llm_tasks: LLMTaskService) -> None:
        self._llm_tasks = llm_tasks

    def parse_prompt(
        self,
        prompt: str,
        *,
        locale_hint: str | None = None,
    ) -> ParsedPreferencesResult:
        locale_currency = currency_from_locale(locale_hint)
        draft = self._llm_tasks.parse_preferences(
            prompt=prompt,
            locale_hint=locale_hint,
            locale_currency=locale_currency,
        )
        return merge_parsed_preferences(draft, locale_currency=locale_currency)
