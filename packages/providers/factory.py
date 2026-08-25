"""Construct provider adapters from environment settings."""

from __future__ import annotations

import os
from dataclasses import dataclass

from packages.providers.apollo_people import ApolloPeopleProvider
from packages.providers.email_finder import EmailFinderProvider
from packages.providers.email_verifier import EmailVerifierProvider
from packages.providers.firecrawl_scraper import FirecrawlScraperProvider
from packages.providers.hunter_email import (
    HunterEmailFinderProvider,
    HunterEmailVerifierProvider,
)
from packages.providers.llm import LLMProvider, MockLLMProvider
from packages.providers.llm_adapters import GeminiLLMProvider, GroqLLMProvider
from packages.providers.mocks import create_mock_providers
from packages.providers.people import PeopleProvider
from packages.providers.scraper import ScraperProvider
from packages.providers.search import SearchProvider
from packages.providers.tavily_search import TavilySearchProvider


@dataclass(frozen=True)
class ProviderSettings:
    llm_provider: str = "groq"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    tavily_api_key: str = ""
    firecrawl_base_url: str = ""
    firecrawl_api_key: str = ""
    apollo_api_key: str = ""
    hunter_api_key: str = ""

    @classmethod
    def from_env(cls) -> ProviderSettings:
        return cls(
            llm_provider=(os.getenv("LLM_PROVIDER") or "groq").strip().lower(),
            groq_api_key=(os.getenv("GROQ_API_KEY") or "").strip(),
            groq_model=(os.getenv("GROQ_MODEL") or "llama-3.3-70b-versatile").strip(),
            gemini_api_key=(os.getenv("GEMINI_API_KEY") or "").strip(),
            gemini_model=(os.getenv("GEMINI_MODEL") or "gemini-2.0-flash").strip(),
            tavily_api_key=(os.getenv("TAVILY_API_KEY") or "").strip(),
            firecrawl_base_url=(os.getenv("FIRECRAWL_BASE_URL") or "").strip().rstrip("/"),
            firecrawl_api_key=(os.getenv("FIRECRAWL_API_KEY") or "").strip(),
            apollo_api_key=(os.getenv("APOLLO_API_KEY") or "").strip(),
            hunter_api_key=(os.getenv("HUNTER_API_KEY") or "").strip(),
        )


def create_search_provider(settings: ProviderSettings | None = None) -> SearchProvider:
    settings = settings or ProviderSettings.from_env()
    if settings.tavily_api_key:
        return TavilySearchProvider(api_key=settings.tavily_api_key)
    return create_mock_providers().search


def create_scraper_provider(settings: ProviderSettings | None = None) -> ScraperProvider:
    settings = settings or ProviderSettings.from_env()
    if settings.firecrawl_base_url:
        return FirecrawlScraperProvider(
            base_url=settings.firecrawl_base_url,
            api_key=settings.firecrawl_api_key or None,
        )
    return create_mock_providers().scraper


def create_llm_provider(settings: ProviderSettings | None = None) -> LLMProvider:
    settings = settings or ProviderSettings.from_env()
    if settings.llm_provider == "gemini" and settings.gemini_api_key:
        return GeminiLLMProvider(
            api_key=settings.gemini_api_key,
            default_model=settings.gemini_model,
        )
    if settings.groq_api_key:
        return GroqLLMProvider(
            api_key=settings.groq_api_key,
            default_model=settings.groq_model,
        )
    return MockLLMProvider()


def create_people_provider(settings: ProviderSettings | None = None) -> PeopleProvider:
    settings = settings or ProviderSettings.from_env()
    if settings.apollo_api_key:
        return ApolloPeopleProvider(api_key=settings.apollo_api_key)
    return create_mock_providers().people


def create_email_finder_provider(
    settings: ProviderSettings | None = None,
) -> EmailFinderProvider:
    settings = settings or ProviderSettings.from_env()
    if settings.hunter_api_key:
        return HunterEmailFinderProvider(api_key=settings.hunter_api_key)
    return create_mock_providers().email_finder


def create_email_verifier_provider(
    settings: ProviderSettings | None = None,
) -> EmailVerifierProvider:
    settings = settings or ProviderSettings.from_env()
    if settings.hunter_api_key:
        return HunterEmailVerifierProvider(api_key=settings.hunter_api_key)
    return create_mock_providers().email_verifier
