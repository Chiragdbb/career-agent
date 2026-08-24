"""PeopleProvider — people / role discovery at a company.

Typical real target (not implemented here): Apollo-style people search.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field, HttpUrl

from packages.providers.base import (
    MockBehavior,
    ProviderMetadata,
    TimeoutMixin,
    UsageInfo,
)


class PeopleSearchRequest(TimeoutMixin):
    company_name: str | None = None
    company_domain: str | None = None
    titles: list[str] = Field(default_factory=list)
    location: str | None = None
    max_results: int = Field(default=10, ge=1, le=100)


class PersonHit(BaseModel):
    full_name: str
    title: str | None = None
    company_name: str | None = None
    linkedin_url: HttpUrl | str | None = None
    location: str | None = None
    raw: dict[str, str] = Field(default_factory=dict)


class PeopleSearchResponse(BaseModel):
    people: list[PersonHit]
    usage: UsageInfo


class PeopleProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError

    @abstractmethod
    def search_people(self, request: PeopleSearchRequest) -> PeopleSearchResponse:
        raise NotImplementedError


class MockPeopleProvider(PeopleProvider):
    def __init__(
        self,
        *,
        people: list[PersonHit] | None = None,
        fail_with: Exception | None = None,
        simulate_timeout: bool = False,
        latency_ms: float = 8.0,
    ) -> None:
        self._people = people or [
            PersonHit(
                full_name="Alex Mock",
                title="Engineering Manager",
                company_name="MockCo",
                linkedin_url="https://www.linkedin.com/in/alex-mock",
            )
        ]
        self._behavior = MockBehavior(
            fail_with=fail_with,
            simulate_timeout=simulate_timeout,
            latency_ms=latency_ms,
            provider_name="mock-people",
        )
        self._meta = ProviderMetadata(
            name="mock-people",
            vendor="mock",
            capabilities=frozenset({"people_search"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def search_people(self, request: PeopleSearchRequest) -> PeopleSearchResponse:
        self._behavior.before_call(
            operation="search_people",
            timeout_seconds=request.timeout_seconds,
        )
        return PeopleSearchResponse(
            people=self._people[: request.max_results],
            usage=self._behavior.usage(operation="search_people", unit_type="credits", units=1.0),
        )
