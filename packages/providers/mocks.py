"""Convenience factory that constructs every mock provider."""

from __future__ import annotations

from dataclasses import dataclass

from packages.providers.browser import MockBrowserProvider
from packages.providers.email_finder import MockEmailFinderProvider
from packages.providers.email_sender import MockEmailSenderProvider
from packages.providers.email_verifier import MockEmailVerifierProvider
from packages.providers.embedding import MockEmbeddingProvider
from packages.providers.llm import MockLLMProvider
from packages.providers.notification import MockNotificationProvider
from packages.providers.people import MockPeopleProvider
from packages.providers.scraper import MockScraperProvider
from packages.providers.search import MockSearchProvider
from packages.providers.storage import MockStorageProvider


@dataclass(frozen=True)
class MockProviders:
    search: MockSearchProvider
    scraper: MockScraperProvider
    llm: MockLLMProvider
    embedding: MockEmbeddingProvider
    people: MockPeopleProvider
    email_finder: MockEmailFinderProvider
    email_verifier: MockEmailVerifierProvider
    browser: MockBrowserProvider
    email_sender: MockEmailSenderProvider
    storage: MockStorageProvider
    notification: MockNotificationProvider


def create_mock_providers() -> MockProviders:
    """Return a full set of mock adapters for tests and local development."""
    return MockProviders(
        search=MockSearchProvider(),
        scraper=MockScraperProvider(),
        llm=MockLLMProvider(),
        embedding=MockEmbeddingProvider(),
        people=MockPeopleProvider(),
        email_finder=MockEmailFinderProvider(),
        email_verifier=MockEmailVerifierProvider(),
        browser=MockBrowserProvider(),
        email_sender=MockEmailSenderProvider(),
        storage=MockStorageProvider(),
        notification=MockNotificationProvider(),
    )
