"""Provider abstraction layer.

Business / domain services must depend on these interfaces only.
Never import a vendor SDK from application or domain code.

Product defaults:
- SearchProvider → Tavily (`TavilySearchProvider`)
- ScraperProvider → self-hosted Firecrawl (`FirecrawlScraperProvider`)
- LLMProvider → Groq or Gemini (`GroqLLMProvider` / `GeminiLLMProvider`)
- StorageProvider → Supabase Storage (`SupabaseStorageProvider`)
- EmailSenderProvider → Resend (`ResendEmailSenderProvider`)
- Auth is Supabase Auth and is intentionally not part of this layer
"""

from __future__ import annotations

from packages.providers.base import (
    DEFAULT_TIMEOUT_SECONDS,
    ProviderMetadata,
    TimeoutMixin,
    UsageInfo,
)
from packages.providers.browser import (
    BrowserAction,
    BrowserActionRequest,
    BrowserActionResponse,
    BrowserActionType,
    BrowserNavigateRequest,
    BrowserProvider,
    BrowserSession,
    BrowserSessionResponse,
    MockBrowserProvider,
)
from packages.providers.email_finder import (
    EmailCandidate,
    EmailFinderProvider,
    EmailFindRequest,
    EmailFindResponse,
    MockEmailFinderProvider,
)
from packages.providers.email_sender import (
    EmailDeliveryState,
    EmailSenderProvider,
    EmailSendRequest,
    EmailSendResponse,
    MockEmailSenderProvider,
    OptionalSesEmailSenderProvider,
    ResendEmailSenderProvider,
    SmtpEmailSenderProvider,
)
from packages.providers.ats import (
    ATSAdapter,
    ATSDetectResult,
    ATSPauseReason,
)
from packages.providers.greenhouse_ats import GreenhouseATSAdapter
from packages.providers.mailbox import (
    EncryptedTokenBlob,
    MailboxConnectionInfo,
    MailboxConnectionStatus,
    MailboxProvider,
    MailboxProviderKind,
    MockMailboxProvider,
    StubGmailMailboxProvider,
    StubOutlookMailboxProvider,
    decrypt_token,
    encrypt_token,
)
from packages.providers.email_verifier import (
    EmailVerificationStatus,
    EmailVerifierProvider,
    EmailVerifyRequest,
    EmailVerifyResponse,
    MockEmailVerifierProvider,
)
from packages.providers.embedding import (
    EmbeddingProvider,
    EmbeddingRequest,
    EmbeddingResponse,
    MockEmbeddingProvider,
)
from packages.providers.exceptions import (
    ProviderAuthError,
    ProviderError,
    ProviderNotConfiguredError,
    ProviderRateLimitError,
    ProviderRateLimitDeferError,
    ProviderStructuredOutputError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from packages.providers.firecrawl_scraper import FirecrawlScraperProvider
from packages.providers.llm import (
    GeminiLLMProvider,
    LLMMessage,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    MockLLMProvider,
)
from packages.providers.llm_adapters import (
    GroqLLMProvider,
    OpenAILLMProvider,
    parse_llm_json,
)
from packages.providers.mocks import MockProviders, create_mock_providers
from packages.providers.notification import (
    MockNotificationProvider,
    NotificationChannel,
    NotificationProvider,
    NotificationSendRequest,
    NotificationSendResponse,
)
from packages.providers.people import (
    MockPeopleProvider,
    PeopleProvider,
    PeopleSearchRequest,
    PeopleSearchResponse,
    PersonHit,
)
from packages.providers.scraper import (
    CrawlRequest,
    CrawlResponse,
    MockScraperProvider,
    ScrapeRequest,
    ScrapeResponse,
    ScrapedPage,
    ScraperProvider,
)
from packages.providers.search import (
    MockSearchProvider,
    SearchHit,
    SearchProvider,
    SearchRequest,
    SearchResponse,
)
from packages.providers.storage import (
    MockStorageProvider,
    StorageDeleteRequest,
    StorageDeleteResponse,
    StorageGetRequest,
    StorageGetResponse,
    StorageObjectResponse,
    StorageProvider,
    StoragePutRequest,
    StorageSignedUrlRequest,
    StorageSignedUrlResponse,
)
from packages.providers.supabase_storage import SupabaseStorageProvider
from packages.providers.tavily_search import TavilySearchProvider

__all__ = [
    "ATSAdapter",
    "ATSDetectResult",
    "ATSPauseReason",
    "DEFAULT_TIMEOUT_SECONDS",
    "BrowserAction",
    "BrowserActionRequest",
    "BrowserActionResponse",
    "BrowserActionType",
    "BrowserNavigateRequest",
    "BrowserProvider",
    "BrowserSession",
    "BrowserSessionResponse",
    "CrawlRequest",
    "CrawlResponse",
    "EmailCandidate",
    "EmailDeliveryState",
    "EmailFindRequest",
    "EmailFindResponse",
    "EmailFinderProvider",
    "EmailSendRequest",
    "EmailSendResponse",
    "EmailSenderProvider",
    "EncryptedTokenBlob",
    "EmailVerificationStatus",
    "EmailVerifierProvider",
    "EmailVerifyRequest",
    "EmailVerifyResponse",
    "EmbeddingProvider",
    "EmbeddingRequest",
    "EmbeddingResponse",
    "FirecrawlScraperProvider",
    "GeminiLLMProvider",
    "GreenhouseATSAdapter",
    "GroqLLMProvider",
    "LLMMessage",
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "MailboxConnectionInfo",
    "MailboxConnectionStatus",
    "MailboxProvider",
    "MailboxProviderKind",
    "MockBrowserProvider",
    "MockEmailFinderProvider",
    "MockEmailSenderProvider",
    "MockEmailVerifierProvider",
    "MockEmbeddingProvider",
    "MockLLMProvider",
    "MockMailboxProvider",
    "MockNotificationProvider",
    "MockPeopleProvider",
    "MockProviders",
    "MockScraperProvider",
    "MockSearchProvider",
    "MockStorageProvider",
    "NotificationChannel",
    "NotificationProvider",
    "NotificationSendRequest",
    "NotificationSendResponse",
    "OpenAILLMProvider",
    "OptionalSesEmailSenderProvider",
    "ResendEmailSenderProvider",
    "PeopleProvider",
    "PeopleSearchRequest",
    "PeopleSearchResponse",
    "PersonHit",
    "ProviderAuthError",
    "ProviderError",
    "ProviderMetadata",
    "ProviderNotConfiguredError",
    "ProviderRateLimitError",
    "ProviderRateLimitDeferError",
    "ProviderStructuredOutputError",
    "ProviderTimeoutError",
    "ProviderUnavailableError",
    "ProviderValidationError",
    "ScrapeRequest",
    "ScrapeResponse",
    "ScrapedPage",
    "ScraperProvider",
    "SearchHit",
    "SearchProvider",
    "SearchRequest",
    "SearchResponse",
    "SmtpEmailSenderProvider",
    "StorageDeleteRequest",
    "StorageDeleteResponse",
    "StorageGetRequest",
    "StorageGetResponse",
    "StorageObjectResponse",
    "StorageProvider",
    "StoragePutRequest",
    "StorageSignedUrlRequest",
    "StorageSignedUrlResponse",
    "StubGmailMailboxProvider",
    "StubOutlookMailboxProvider",
    "SupabaseStorageProvider",
    "TavilySearchProvider",
    "TimeoutMixin",
    "UsageInfo",
    "create_mock_providers",
    "decrypt_token",
    "encrypt_token",
    "parse_llm_json",
]
