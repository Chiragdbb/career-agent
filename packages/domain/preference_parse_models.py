"""Models and merge helpers for preference prompt parsing (no LLM imports)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from packages.domain.preferences import (
    CompanySize,
    EmploymentType,
    JobFreshness,
    PreferenceSettings,
    SeniorityLevel,
    WorkArrangement,
)

_SUPPORTED_CURRENCIES = frozenset({
    "USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD", "CNY", "HKD", "SGD",
    "INR", "KRW", "MXN", "BRL", "ZAR", "SEK", "NOK", "DKK", "PLN", "TRY", "AED",
    "SAR", "THB", "MYR", "PHP", "IDR", "TWD", "PKR", "ILS", "CZK", "HUF", "RON",
    "BGN", "COP", "CLP", "ARS", "EGP", "NGN", "VND", "UAH",
})

_LOCALE_REGION_CURRENCY: dict[str, str] = {
    "us": "USD",
    "gb": "GBP",
    "uk": "GBP",
    "in": "INR",
    "au": "AUD",
    "ca": "CAD",
    "sg": "SGD",
    "de": "EUR",
    "fr": "EUR",
    "es": "EUR",
    "it": "EUR",
    "nl": "EUR",
    "ie": "EUR",
}


class PreferenceParseDraft(BaseModel):
    """Lenient LLM output before merging into PreferenceSettings."""

    target_roles: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    work_arrangements: list[str] = Field(default_factory=list)
    minimum_salary: int | None = None
    salary_currency: str | None = None
    seniority: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    company_sizes: list[str] = Field(default_factory=list)
    employment_types: list[str] = Field(default_factory=list)
    job_freshness: str | None = None
    unparsed_notes: list[str] = Field(default_factory=list)


class ParsedPreferencesResult(BaseModel):
    settings: PreferenceSettings
    unparsed_notes: list[str] = Field(default_factory=list)


def currency_from_locale(locale_hint: str | None) -> str:
    if not locale_hint:
        return "USD"
    normalized = locale_hint.strip().lower().replace("_", "-")
    parts = normalized.split("-")
    region = parts[-1] if len(parts) > 1 else parts[0]
    currency = _LOCALE_REGION_CURRENCY.get(region, "USD")
    return currency if currency in _SUPPORTED_CURRENCIES else "USD"


def _filter_enum_values(values: list[str], enum_cls: type) -> list:
    allowed = {item.value for item in enum_cls}
    return [enum_cls(value) for value in values if value in allowed]


def merge_parsed_preferences(
    draft: PreferenceParseDraft,
    *,
    locale_currency: str = "USD",
) -> ParsedPreferencesResult:
    """Merge LLM draft into validated PreferenceSettings."""
    base = PreferenceSettings()
    updates: dict[str, object] = {}

    if draft.target_roles:
        updates["target_roles"] = draft.target_roles
    if draft.locations:
        updates["locations"] = draft.locations
    if draft.work_arrangements:
        filtered = _filter_enum_values(draft.work_arrangements, WorkArrangement)
        if filtered:
            updates["work_arrangements"] = filtered
    if draft.minimum_salary is not None:
        updates["minimum_salary"] = draft.minimum_salary
    if draft.salary_currency:
        currency = draft.salary_currency.strip().upper()
        if currency in _SUPPORTED_CURRENCIES:
            updates["salary_currency"] = currency
    elif draft.minimum_salary is not None:
        fallback = locale_currency.upper() if locale_currency else "USD"
        updates["salary_currency"] = (
            fallback if fallback in _SUPPORTED_CURRENCIES else "USD"
        )
    if draft.seniority:
        filtered = _filter_enum_values(draft.seniority, SeniorityLevel)
        if filtered:
            updates["seniority"] = filtered
    if draft.industries:
        updates["industries"] = draft.industries
    if draft.company_sizes:
        filtered = _filter_enum_values(draft.company_sizes, CompanySize)
        if filtered:
            updates["company_sizes"] = filtered
    if draft.employment_types:
        filtered = _filter_enum_values(draft.employment_types, EmploymentType)
        if filtered:
            updates["employment_types"] = filtered
    if draft.job_freshness and draft.job_freshness in {item.value for item in JobFreshness}:
        updates["job_freshness"] = JobFreshness(draft.job_freshness)

    settings = PreferenceSettings.model_validate(
        {**base.model_dump(mode="json"), **updates}
    )
    return ParsedPreferencesResult(
        settings=settings,
        unparsed_notes=list(draft.unparsed_notes),
    )
