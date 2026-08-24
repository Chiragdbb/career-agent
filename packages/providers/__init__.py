"""Provider abstraction layer.

Business / domain services must depend on these interfaces only.
Never import a vendor SDK from application or domain code.

Product defaults (adapters not implemented in this package yet):
- SearchProvider → Tavily
- ScraperProvider → self-hosted Firecrawl
- LLMProvider → Groq or Gemini
- StorageProvider → Supabase Storage (private buckets, signed URLs)
- Auth is Supabase Auth and is intentionally not part of this layer

Import examples (repo root on PYTHONPATH — pytest conftest already configures this)::

    from packages.providers import SearchProvider, MockSearchProvider, SearchRequest
    from packages.providers import create_mock_providers

    mocks = create_mock_providers()
    response = mocks.search.search(SearchRequest(query="software engineer bangalore"))
"""

from __future__ import annotations

from packages.providers.base import (
    DEFAULT_TIMEOUT_SECONDS,
    ProviderMetadata,
    TimeoutMixin,
    UsageInfo,
)
from packages.providers.browser import (
    BrowserActionRequest,
    BrowserActionResponse,
    BrowserNavigateRequest,
    BrowserProvider,
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
    EmailSenderProvider,
    EmailSendRequest,
    EmailSendResponse,
    MockEmailSenderProvider,
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
    ProviderTimeoutError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from packages.providers.llm import (
    LLMMessage,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    MockLLMProvider,
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
    MockScraperProvider,
    ScrapeRequest,
    ScrapeResponse,
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

__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "BrowserActionRequest",
    "BrowserActionResponse",
    "BrowserNavigateRequest",
    "BrowserProvider",
    "BrowserSessionResponse",
    "EmailCandidate",
    "EmailFindRequest",
    "EmailFindResponse",
    "EmailFinderProvider",
    "EmailSendRequest",
    "EmailSendResponse",
    "EmailSenderProvider",
    "EmailVerificationStatus",
    "EmailVerifierProvider",
    "EmailVerifyRequest",
    "EmailVerifyResponse",
    "EmbeddingProvider",
    "EmbeddingRequest",
    "EmbeddingResponse",
    "LLMMessage",
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "MockBrowserProvider",
    "MockEmailFinderProvider",
    "MockEmailSenderProvider",
    "MockEmailVerifierProvider",
    "MockEmbeddingProvider",
    "MockLLMProvider",
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
    "PeopleProvider",
    "PeopleSearchRequest",
    "PeopleSearchResponse",
    "PersonHit",
    "ProviderAuthError",
    "ProviderError",
    "ProviderMetadata",
    "ProviderNotConfiguredError",
    "ProviderRateLimitError",
    "ProviderTimeoutError",
    "ProviderUnavailableError",
    "ProviderValidationError",
    "ScrapeRequest",
    "ScrapeResponse",
    "ScraperProvider",
    "SearchHit",
    "SearchProvider",
    "SearchRequest",
    "SearchResponse",
    "StorageDeleteRequest",
    "StorageDeleteResponse",
    "StorageGetRequest",
    "StorageGetResponse",
    "StorageObjectResponse",
    "StorageProvider",
    "StoragePutRequest",
    "StorageSignedUrlRequest",
    "StorageSignedUrlResponse",
    "TimeoutMixin",
    "UsageInfo",
    "create_mock_providers",
]
