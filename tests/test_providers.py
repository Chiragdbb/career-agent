"""Unit tests for provider mocks: happy path, timeouts, errors, usage metadata."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from packages.providers import (
    DEFAULT_TIMEOUT_SECONDS,
    BrowserActionRequest,
    BrowserNavigateRequest,
    EmailFindRequest,
    EmailSendRequest,
    EmailVerifyRequest,
    EmbeddingRequest,
    LLMMessage,
    LLMRequest,
    MockBrowserProvider,
    MockEmailFinderProvider,
    MockEmailSenderProvider,
    MockEmailVerifierProvider,
    MockEmbeddingProvider,
    MockLLMProvider,
    MockNotificationProvider,
    MockPeopleProvider,
    MockScraperProvider,
    MockSearchProvider,
    MockStorageProvider,
    NotificationChannel,
    NotificationSendRequest,
    PeopleSearchRequest,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderValidationError,
    ScrapeRequest,
    SearchRequest,
    StorageGetRequest,
    StoragePutRequest,
    StorageSignedUrlRequest,
    create_mock_providers,
)


def test_create_mock_providers_exposes_all_interfaces() -> None:
    mocks = create_mock_providers()
    assert mocks.search.metadata.vendor == "mock"
    assert mocks.scraper.metadata.name == "mock-scraper"
    assert mocks.llm.metadata.capabilities
    assert mocks.embedding.metadata.vendor == "mock"
    assert mocks.people.metadata.vendor == "mock"
    assert mocks.email_finder.metadata.vendor == "mock"
    assert mocks.email_verifier.metadata.vendor == "mock"
    assert mocks.browser.metadata.vendor == "mock"
    assert mocks.email_sender.metadata.vendor == "mock"
    assert mocks.storage.metadata.vendor == "mock"
    assert mocks.notification.metadata.vendor == "mock"


def test_search_mock_returns_usage_and_respects_max_results() -> None:
    provider = MockSearchProvider()
    response = provider.search(SearchRequest(query="python jobs", max_results=1))
    assert len(response.results) == 1
    assert response.usage.provider == "mock-search"
    assert response.usage.operation == "search"
    assert response.usage.latency_ms is not None
    assert SearchRequest(query="timeout-default").timeout_seconds == DEFAULT_TIMEOUT_SECONDS


def test_search_mock_timeout() -> None:
    provider = MockSearchProvider(simulate_timeout=True)
    with pytest.raises(ProviderTimeoutError) as exc:
        provider.search(SearchRequest(query="x", timeout_seconds=0.01))
    assert exc.value.provider == "mock-search"
    assert exc.value.operation == "search"


def test_search_mock_rate_limit() -> None:
    provider = MockSearchProvider(
        fail_with=ProviderRateLimitError("slow down", provider="mock-search", operation="search")
    )
    with pytest.raises(ProviderRateLimitError):
        provider.search(SearchRequest(query="x"))


def test_scraper_and_llm_mocks() -> None:
    scrape = MockScraperProvider().scrape(ScrapeRequest(url="https://example.com"))
    assert "Mock" in scrape.markdown
    assert scrape.usage.unit_type == "pages"

    llm = MockLLMProvider(content='{"role":"ok"}').complete(
        LLMRequest(messages=[LLMMessage(role="user", content="hi")])
    )
    assert llm.content.startswith("{")
    assert llm.usage.unit_type == "tokens"
    assert llm.usage.extra["prompt_tokens"] == 10.0


def test_mock_llm_returns_valid_extract_job_payload() -> None:
    llm = MockLLMProvider()
    response = llm.complete(
        LLMRequest(
            messages=[
                LLMMessage(role="system", content="Extract structured job fields"),
                LLMMessage(role="user", content="URL: https://jobs.example.com/mock/backend\n\nMARKDOWN:\n# Job"),
            ]
        )
    )
    payload = json.loads(response.content)
    assert payload["title"]
    assert payload["url"] == "https://jobs.example.com/mock/backend"


def test_mock_search_generates_unique_urls_per_query() -> None:
    provider = MockSearchProvider()
    first = provider.search(SearchRequest(query="python jobs remote", max_results=1))
    second = provider.search(SearchRequest(query="java jobs bangalore", max_results=1))
    assert first.results[0].url != second.results[0].url


def test_embedding_mock_dimensions() -> None:
    response = MockEmbeddingProvider().embed(
        EmbeddingRequest(texts=["a", "b"], dimensions=8)
    )
    assert len(response.embeddings) == 2
    assert len(response.embeddings[0]) == 8
    assert response.usage.operation == "embed"


def test_people_email_and_notification_mocks() -> None:
    people = MockPeopleProvider().search_people(PeopleSearchRequest(company_name="MockCo"))
    assert people.people[0].full_name
    assert people.usage.unit_type == "credits"

    found = MockEmailFinderProvider().find_email(
        EmailFindRequest(full_name="Alex Mock", company_domain="example.com")
    )
    assert found.candidates[0].email.endswith("@example.com")

    verified = MockEmailVerifierProvider().verify_email(
        EmailVerifyRequest(email="alex.mock@example.com")
    )
    assert verified.status.value == "valid"

    notif = MockNotificationProvider()
    sent = notif.send(
        NotificationSendRequest(
            user_id=uuid4(),
            channel=NotificationChannel.in_app,
            title="Hello",
            body="World",
        )
    )
    assert sent.delivered is True
    assert len(notif.sent) == 1


def test_browser_and_email_sender_mocks() -> None:
    browser = MockBrowserProvider()
    session = browser.navigate(BrowserNavigateRequest(url="https://example.com/jobs"))
    action = browser.action(
        BrowserActionRequest(session_id=session.session_id, action="extract", selector="body")
    )
    assert action.ok is True
    assert action.extracted_text

    sender = MockEmailSenderProvider()
    result = sender.send_email(
        EmailSendRequest(to=["hiring@example.com"], subject="Intro", body_text="Hi")
    )
    assert result.message_id
    assert len(sender.sent) == 1


def test_storage_mock_roundtrip_and_signed_url() -> None:
    storage = MockStorageProvider()
    put = storage.put_object(
        StoragePutRequest(
            bucket="docs",
            key="resume.pdf",
            data=b"%PDF-mock",
            content_type="application/pdf",
        )
    )
    assert put.size_bytes == 9
    got = storage.get_object(StorageGetRequest(bucket="docs", key="resume.pdf"))
    assert got.data.startswith(b"%PDF")
    signed = storage.create_signed_url(
        StorageSignedUrlRequest(bucket="docs", key="resume.pdf", expires_in_seconds=60)
    )
    assert "sig=mock" in str(signed.url)
    assert signed.usage.operation == "create_signed_url"


def test_storage_missing_object_raises_validation_error() -> None:
    storage = MockStorageProvider()
    with pytest.raises(ProviderValidationError):
        storage.get_object(StorageGetRequest(bucket="docs", key="missing"))


def test_llm_timeout_and_embedding_timeout() -> None:
    with pytest.raises(ProviderTimeoutError):
        MockLLMProvider(simulate_timeout=True).complete(
            LLMRequest(messages=[LLMMessage(role="user", content="hi")])
        )
    with pytest.raises(ProviderTimeoutError):
        MockEmbeddingProvider(simulate_timeout=True).embed(EmbeddingRequest(texts=["x"]))
