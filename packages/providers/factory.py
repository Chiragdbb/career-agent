"""Construct provider adapters from environment settings."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from packages.providers.apollo_people import ApolloPeopleProvider
from packages.providers.email_finder import EmailFinderProvider
from packages.providers.email_verifier import EmailVerifierProvider
from packages.providers.firecrawl_scraper import FirecrawlScraperProvider
from packages.providers.groq_models import DEFAULT_GROQ_MODEL, normalize_groq_model
from packages.providers.hunter_email import (
    HunterEmailFinderProvider,
    HunterEmailVerifierProvider,
)
from packages.providers.llm import GeminiLLMProvider, LLMProvider, MockLLMProvider
from packages.providers.llm.gemini_config import (
    GEMINI_DEFAULT_MODEL,
    GEMINI_EXTRACTION_MODEL,
    gemini_rpm_for_tier,
    normalize_gemini_tier,
)
from packages.providers.llm.gemini_rate_limiter import (
    InMemoryGeminiRateLimiter,
    RedisGeminiRateLimiter,
)
from packages.providers.llm_adapters import GroqLLMProvider, OpenAILLMProvider
from packages.providers.mocks import create_mock_providers
from packages.providers.people import PeopleProvider
from packages.providers.scraper import ScraperProvider
from packages.providers.scraper_fallback import FallbackScraperProvider
from packages.providers.search import SearchProvider
from packages.providers.tavily_search import TavilySearchProvider

logger = logging.getLogger("career.providers")

FIRECRAWL_CLOUD_URL = "https://api.firecrawl.dev"


@dataclass(frozen=True)
class ProviderSettings:
    llm_provider: str = "groq"
    groq_api_key: str = ""
    groq_model: str = DEFAULT_GROQ_MODEL
    gemini_api_key: str = ""
    gemini_model: str = GEMINI_DEFAULT_MODEL
    gemini_extraction_model: str = GEMINI_EXTRACTION_MODEL
    gemini_tier: str = "free"
    gemini_rpm_limit: int = 10
    gemini_rate_limit_max_retries: int = 3
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    extraction_llm_provider: str = ""
    extraction_llm_model: str = ""
    tavily_api_key: str = ""
    firecrawl_base_url: str = ""
    firecrawl_api_key: str = ""
    apollo_api_key: str = ""
    hunter_api_key: str = ""
    resend_api_key: str = ""
    resend_from_email: str = ""

    @classmethod
    def from_env(cls) -> ProviderSettings:
        gemini_tier = normalize_gemini_tier(os.getenv("GEMINI_TIER"))
        return cls(
            llm_provider=(os.getenv("LLM_PROVIDER") or "groq").strip().lower(),
            groq_api_key=(os.getenv("GROQ_API_KEY") or "").strip(),
            groq_model=normalize_groq_model(os.getenv("GROQ_MODEL") or DEFAULT_GROQ_MODEL),
            gemini_api_key=(os.getenv("GEMINI_API_KEY") or "").strip(),
            gemini_model=(os.getenv("GEMINI_MODEL") or GEMINI_DEFAULT_MODEL).strip(),
            gemini_extraction_model=(
                os.getenv("GEMINI_EXTRACTION_MODEL") or GEMINI_EXTRACTION_MODEL
            ).strip(),
            gemini_tier=gemini_tier,
            gemini_rpm_limit=gemini_rpm_for_tier(gemini_tier),
            gemini_rate_limit_max_retries=int(os.getenv("GEMINI_RATE_LIMIT_MAX_RETRIES") or "3"),
            openai_api_key=(os.getenv("OPENAI_API_KEY") or "").strip(),
            openai_model=(os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip(),
            extraction_llm_provider=(os.getenv("EXTRACTION_LLM_PROVIDER") or "").strip().lower(),
            extraction_llm_model=(os.getenv("EXTRACTION_LLM_MODEL") or "").strip(),
            tavily_api_key=(os.getenv("TAVILY_API_KEY") or "").strip(),
            firecrawl_base_url=(os.getenv("FIRECRAWL_BASE_URL") or "").strip().rstrip("/"),
            firecrawl_api_key=(os.getenv("FIRECRAWL_API_KEY") or "").strip(),
            apollo_api_key=(os.getenv("APOLLO_API_KEY") or "").strip(),
            hunter_api_key=(os.getenv("HUNTER_API_KEY") or "").strip(),
            resend_api_key=(os.getenv("RESEND_API_KEY") or "").strip(),
            resend_from_email=(os.getenv("RESEND_FROM_EMAIL") or "").strip(),
        )


def create_search_provider(settings: ProviderSettings | None = None) -> SearchProvider:
    settings = settings or ProviderSettings.from_env()
    if settings.tavily_api_key:
        return TavilySearchProvider(api_key=settings.tavily_api_key)
    return create_mock_providers().search


def create_scraper_provider(settings: ProviderSettings | None = None) -> ScraperProvider:
    settings = settings or ProviderSettings.from_env()
    scrapers: list[ScraperProvider] = []

    if settings.firecrawl_base_url:
        scrapers.append(
            FirecrawlScraperProvider(
                base_url=settings.firecrawl_base_url,
                api_key=settings.firecrawl_api_key or None,
            )
        )

    cloud_configured = bool(settings.firecrawl_api_key) and (
        not settings.firecrawl_base_url
        or settings.firecrawl_base_url.rstrip("/") != FIRECRAWL_CLOUD_URL
    )
    if cloud_configured:
        scrapers.append(
            FirecrawlScraperProvider(
                base_url=FIRECRAWL_CLOUD_URL,
                api_key=settings.firecrawl_api_key,
            )
        )

    if not scrapers:
        return create_mock_providers().scraper
    if len(scrapers) == 1:
        return scrapers[0]
    return FallbackScraperProvider(scrapers)


def _try_get_redis():
    try:
        from app.redis import get_redis

        return get_redis()
    except Exception:
        logger.warning("redis_unavailable_for_gemini_rate_limiter", exc_info=True)
        return None


def _create_gemini_provider(settings: ProviderSettings) -> GeminiLLMProvider:
    redis_client = _try_get_redis()
    if redis_client is not None:
        rate_limiter = RedisGeminiRateLimiter(
            redis_client,
            rpm_limit=settings.gemini_rpm_limit,
            gemini_tier=settings.gemini_tier,
        )
    else:
        rate_limiter = InMemoryGeminiRateLimiter(
            rpm_limit=settings.gemini_rpm_limit,
            gemini_tier=settings.gemini_tier,
        )
    return GeminiLLMProvider(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        extraction_model=settings.gemini_extraction_model,
        rate_limiter=rate_limiter,
        gemini_tier=settings.gemini_tier,
        rpm_limit=settings.gemini_rpm_limit,
        rate_limit_max_retries=settings.gemini_rate_limit_max_retries,
    )


def create_llm_provider(settings: ProviderSettings | None = None) -> LLMProvider:
    settings = settings or ProviderSettings.from_env()
    if settings.llm_provider == "openai" and settings.openai_api_key:
        return OpenAILLMProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
    if settings.llm_provider == "gemini" and settings.gemini_api_key:
        return _create_gemini_provider(settings)
    if settings.groq_api_key:
        model = normalize_groq_model(settings.groq_model)
        if model != settings.groq_model:
            logger.warning(
                "GROQ_MODEL %r is deprecated; using %r instead",
                settings.groq_model,
                model,
            )
        return GroqLLMProvider(
            api_key=settings.groq_api_key,
            model=model,
        )
    if settings.openai_api_key:
        return OpenAILLMProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
    return MockLLMProvider()


def create_extraction_llm_provider(settings: ProviderSettings | None = None) -> LLMProvider:
    """LLM for job extraction — prefers OpenAI structured output when configured."""
    settings = settings or ProviderSettings.from_env()
    provider = settings.extraction_llm_provider or (
        "openai" if settings.openai_api_key else settings.llm_provider
    )
    model = settings.extraction_llm_model or settings.openai_model

    if provider == "openai" and settings.openai_api_key:
        return OpenAILLMProvider(api_key=settings.openai_api_key, model=model)
    if provider == "gemini" and settings.gemini_api_key:
        return _create_gemini_provider(settings)
    if provider == "groq" and settings.groq_api_key:
        groq_model = normalize_groq_model(
            settings.extraction_llm_model or settings.groq_model
        )
        return GroqLLMProvider(api_key=settings.groq_api_key, model=groq_model)
    return create_llm_provider(settings)


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


def create_email_sender_provider(
    settings: ProviderSettings | None = None,
):
    """Resend when RESEND_API_KEY is set; else optional SMTP; else mock (CI-safe)."""
    from packages.providers.email_sender import (
        MockEmailSenderProvider,
        OptionalSesEmailSenderProvider,
        ResendEmailSenderProvider,
        SmtpEmailSenderProvider,
    )

    settings = settings or ProviderSettings.from_env()
    if settings.resend_api_key:
        return ResendEmailSenderProvider(
            api_key=settings.resend_api_key,
            from_email=settings.resend_from_email,
        )
    smtp_host = (os.getenv("SMTP_HOST") or "").strip()
    if smtp_host:
        return SmtpEmailSenderProvider(
            host=smtp_host,
            port=int(os.getenv("SMTP_PORT") or "587"),
            username=(os.getenv("SMTP_USERNAME") or "").strip() or None,
            password=(os.getenv("SMTP_PASSWORD") or "").strip() or None,
            use_tls=(os.getenv("SMTP_USE_TLS") or "true").strip().lower()
            in ("1", "true", "yes"),
            from_email=(os.getenv("SMTP_FROM_EMAIL") or "").strip() or "noreply@localhost",
        )
    if (os.getenv("SES_ENABLED") or "").strip().lower() in ("1", "true", "yes"):
        return OptionalSesEmailSenderProvider(
            region=(os.getenv("SES_REGION") or "").strip(),
            access_key_id=(os.getenv("AWS_ACCESS_KEY_ID") or "").strip(),
            secret_access_key=(os.getenv("AWS_SECRET_ACCESS_KEY") or "").strip(),
            from_email=(os.getenv("SES_FROM_EMAIL") or "").strip(),
            enabled=True,
        )
    return MockEmailSenderProvider()


def log_active_providers(settings: ProviderSettings | None = None) -> dict[str, str]:
    """Log which provider adapters are active (real vs mock)."""
    settings = settings or ProviderSettings.from_env()
    active = {
        "search": create_search_provider(settings).metadata.name,
        "scraper": create_scraper_provider(settings).metadata.name,
        "llm": create_llm_provider(settings).metadata.name,
        "extraction_llm": create_extraction_llm_provider(settings).metadata.name,
        "people": create_people_provider(settings).metadata.name,
        "email_finder": create_email_finder_provider(settings).metadata.name,
        "email_verifier": create_email_verifier_provider(settings).metadata.name,
        "email_sender": create_email_sender_provider(settings).metadata.name,
    }
    for capability, name in active.items():
        kind = "mock" if name.startswith("mock-") else "live"
        logger.info("provider %s=%s (%s)", capability, name, kind)
    mocks = [cap for cap, name in active.items() if name.startswith("mock-")]
    if mocks and os.getenv("APP_ENV", "development") != "test":
        logger.warning(
            "Using mock providers for: %s — set API keys in root .env for live data",
            ", ".join(mocks),
        )
    return active
