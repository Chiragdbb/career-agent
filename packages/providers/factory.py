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
from packages.providers.exceptions import ProviderNotConfiguredError
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


def mocks_allowed() -> bool:
    """Mocks only when APP_ENV=test and ALLOW_MOCK_PROVIDERS is truthy."""
    env = os.getenv("APP_ENV", "development").strip().lower()
    allow = os.getenv("ALLOW_MOCK_PROVIDERS", "").strip().lower() in ("1", "true", "yes")
    return env == "test" and allow


def _require_live(capability: str, missing: list[str]) -> None:
    raise ProviderNotConfiguredError(
        f"{capability} provider is not configured; set {', '.join(missing)} "
        f"(mocks only when APP_ENV=test and ALLOW_MOCK_PROVIDERS=1)",
        provider=capability,
        operation="create",
        details={"missing_env": missing},
    )


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
    embedding_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_dimensions: int = 1536

    @classmethod
    def from_env(cls) -> ProviderSettings:
        gemini_tier = normalize_gemini_tier(os.getenv("GEMINI_TIER"))
        embedding_key = (
            (os.getenv("EMBEDDING_API_KEY") or "").strip()
            or (os.getenv("OPENAI_API_KEY") or "").strip()
        )
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
            embedding_api_key=embedding_key,
            embedding_model=(os.getenv("EMBEDDING_MODEL") or "text-embedding-3-small").strip(),
            embedding_base_url=(
                os.getenv("EMBEDDING_BASE_URL") or "https://api.openai.com/v1"
            ).strip().rstrip("/"),
            embedding_dimensions=int(os.getenv("EMBEDDING_DIMENSIONS") or "1536"),
        )


def create_search_provider(settings: ProviderSettings | None = None) -> SearchProvider:
    settings = settings or ProviderSettings.from_env()
    if settings.tavily_api_key:
        return TavilySearchProvider(api_key=settings.tavily_api_key)
    if mocks_allowed():
        return create_mock_providers().search
    _require_live("search", ["TAVILY_API_KEY"])


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
        if mocks_allowed():
            return create_mock_providers().scraper
        _require_live("scraper", ["FIRECRAWL_BASE_URL", "FIRECRAWL_API_KEY"])
    if len(scrapers) == 1:
        return scrapers[0]
    return FallbackScraperProvider(scrapers)


def create_playwright_jobs_provider(settings: ProviderSettings | None = None):
    """Primary free job scraper for known boards.

    Returns None when Playwright cannot be initialized so discovery can continue
    with Firecrawl-only scraping. Mocks are only used when ALLOW_MOCK_PROVIDERS
    is set under APP_ENV=test.
    """
    _ = settings or ProviderSettings.from_env()
    try:
        from packages.providers.playwright_jobs import PlaywrightJobsProvider

        return PlaywrightJobsProvider()
    except Exception as exc:
        if mocks_allowed():
            try:
                from packages.providers.playwright_jobs import MockPlaywrightJobsProvider

                logger.info("playwright_jobs_unavailable_using_mock error=%s", exc)
                return MockPlaywrightJobsProvider()
            except Exception:
                logger.warning("playwright_jobs_mock_unavailable", exc_info=True)
                return None
        logger.warning(
            "playwright_jobs_unavailable continuing without it error=%s",
            exc,
        )
        return None


def create_playwright_contacts_provider(settings: ProviderSettings | None = None):
    _ = settings or ProviderSettings.from_env()
    try:
        from packages.providers.playwright_contacts import PlaywrightContactsProvider

        return PlaywrightContactsProvider()
    except Exception as exc:
        if mocks_allowed():
            try:
                from packages.providers.playwright_contacts import (
                    MockPlaywrightContactsProvider,
                )

                logger.info("playwright_contacts_unavailable_using_mock error=%s", exc)
                return MockPlaywrightContactsProvider()
            except Exception:
                logger.warning("playwright_contacts_mock_unavailable", exc_info=True)
                return None
        logger.warning(
            "playwright_contacts_unavailable continuing without it error=%s",
            exc,
        )
        return None


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
    if settings.gemini_api_key:
        return _create_gemini_provider(settings)
    if mocks_allowed():
        return MockLLMProvider()
    missing = ["GROQ_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"]
    if settings.llm_provider == "openai":
        missing = ["OPENAI_API_KEY"]
    elif settings.llm_provider == "gemini":
        missing = ["GEMINI_API_KEY"]
    elif settings.llm_provider == "groq":
        missing = ["GROQ_API_KEY"]
    _require_live("llm", missing)


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
    if mocks_allowed():
        return create_mock_providers().people
    _require_live("people", ["APOLLO_API_KEY"])


def create_email_finder_provider(
    settings: ProviderSettings | None = None,
) -> EmailFinderProvider:
    settings = settings or ProviderSettings.from_env()
    if settings.hunter_api_key:
        return HunterEmailFinderProvider(api_key=settings.hunter_api_key)
    if mocks_allowed():
        return create_mock_providers().email_finder
    _require_live("email_finder", ["HUNTER_API_KEY"])


def create_email_verifier_provider(
    settings: ProviderSettings | None = None,
) -> EmailVerifierProvider:
    settings = settings or ProviderSettings.from_env()
    if settings.hunter_api_key:
        return HunterEmailVerifierProvider(api_key=settings.hunter_api_key)
    if mocks_allowed():
        return create_mock_providers().email_verifier
    _require_live("email_verifier", ["HUNTER_API_KEY"])


def create_embedding_provider(settings: ProviderSettings | None = None):
    """OpenAI-compatible embeddings when keyed."""
    from packages.providers.embedding import OpenAICompatibleEmbeddingProvider

    settings = settings or ProviderSettings.from_env()
    if settings.embedding_api_key:
        return OpenAICompatibleEmbeddingProvider(
            api_key=settings.embedding_api_key,
            model=settings.embedding_model,
            base_url=settings.embedding_base_url,
            dimensions=settings.embedding_dimensions,
        )
    if mocks_allowed():
        return create_mock_providers().embedding
    _require_live("embedding", ["EMBEDDING_API_KEY", "OPENAI_API_KEY"])


def create_email_sender_provider(
    settings: ProviderSettings | None = None,
):
    """Resend when RESEND_API_KEY is set; else optional SMTP/SES."""
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
    if mocks_allowed():
        return MockEmailSenderProvider()
    _require_live("email_sender", ["RESEND_API_KEY", "SMTP_HOST", "SES_ENABLED"])


def log_active_providers(settings: ProviderSettings | None = None) -> dict[str, str]:
    """Log which provider adapters are active (skips capabilities that are not configured)."""
    settings = settings or ProviderSettings.from_env()
    creators = {
        "search": create_search_provider,
        "scraper": create_scraper_provider,
        "llm": create_llm_provider,
        "extraction_llm": create_extraction_llm_provider,
        "people": create_people_provider,
        "email_finder": create_email_finder_provider,
        "email_verifier": create_email_verifier_provider,
        "email_sender": create_email_sender_provider,
        "embedding": create_embedding_provider,
    }
    active: dict[str, str] = {}
    missing: list[str] = []
    for capability, create in creators.items():
        try:
            name = create(settings).metadata.name
            active[capability] = name
            kind = "mock" if name.startswith("mock-") else "live"
            logger.info("provider %s=%s (%s)", capability, name, kind)
        except ProviderNotConfiguredError as exc:
            missing.append(capability)
            logger.info(
                "provider %s=unconfigured missing=%s",
                capability,
                (exc.details or {}).get("missing_env"),
            )
    if missing:
        logger.warning(
            "Providers not configured (will fail if used): %s — set API keys in root .env",
            ", ".join(missing),
        )
    return active
