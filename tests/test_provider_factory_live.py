"""Factory must fail loud unless APP_ENV=test and ALLOW_MOCK_PROVIDERS=1."""

from __future__ import annotations

import pytest

from packages.providers.exceptions import ProviderNotConfiguredError
from packages.providers.factory import (
    ProviderSettings,
    create_llm_provider,
    create_scraper_provider,
    create_search_provider,
    mocks_allowed,
)


def test_mocks_allowed_only_in_test_with_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ALLOW_MOCK_PROVIDERS", "1")
    assert mocks_allowed() is False

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.delenv("ALLOW_MOCK_PROVIDERS", raising=False)
    assert mocks_allowed() is False

    monkeypatch.setenv("ALLOW_MOCK_PROVIDERS", "1")
    assert mocks_allowed() is True


def test_create_search_raises_without_tavily(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("ALLOW_MOCK_PROVIDERS", raising=False)
    settings = ProviderSettings(tavily_api_key="")
    with pytest.raises(ProviderNotConfiguredError) as exc:
        create_search_provider(settings)
    assert "TAVILY_API_KEY" in str(exc.value)


def test_create_scraper_raises_without_firecrawl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("ALLOW_MOCK_PROVIDERS", raising=False)
    settings = ProviderSettings(firecrawl_base_url="", firecrawl_api_key="")
    with pytest.raises(ProviderNotConfiguredError) as exc:
        create_scraper_provider(settings)
    assert "FIRECRAWL" in str(exc.value)


def test_create_llm_raises_without_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("ALLOW_MOCK_PROVIDERS", raising=False)
    settings = ProviderSettings(
        llm_provider="groq",
        groq_api_key="",
        openai_api_key="",
        gemini_api_key="",
    )
    with pytest.raises(ProviderNotConfiguredError):
        create_llm_provider(settings)


def test_create_search_allows_mock_in_test(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("ALLOW_MOCK_PROVIDERS", "1")
    settings = ProviderSettings(tavily_api_key="")
    provider = create_search_provider(settings)
    assert provider.metadata.name.startswith("mock-")
