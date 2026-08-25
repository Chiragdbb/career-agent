"""Apollo-style PeopleProvider adapter.

Requires APOLLO_API_KEY. Without a key, factory falls back to MockPeopleProvider.
This stub performs real HTTP only when configured; CI uses mocks.
"""

from __future__ import annotations

from typing import Any

from packages.providers.base import ProviderMetadata, UsageInfo
from packages.providers.exceptions import (
    ProviderNotConfiguredError,
    ProviderValidationError,
)
from packages.providers.http_utils import request_with_retries
from packages.providers.people import (
    PeopleProvider,
    PeopleSearchRequest,
    PeopleSearchResponse,
    PersonHit,
)


class ApolloPeopleProvider(PeopleProvider):
    """Thin Apollo people-search adapter behind PeopleProvider."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.apollo.io/v1",
        timeout_seconds: float = 30.0,
    ) -> None:
        key = (api_key or "").strip()
        if not key:
            raise ProviderNotConfiguredError(
                "APOLLO_API_KEY is required for ApolloPeopleProvider",
                provider="apollo-people",
            )
        self._api_key = key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._meta = ProviderMetadata(
            name="apollo-people",
            vendor="apollo",
            capabilities=frozenset({"people_search"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def search_people(self, request: PeopleSearchRequest) -> PeopleSearchResponse:
        payload: dict[str, Any] = {
            "q_organization_name": request.company_name,
            "organization_domains": [request.company_domain] if request.company_domain else [],
            "person_titles": request.titles,
            "page": 1,
            "per_page": request.max_results,
        }
        response = request_with_retries(
            method="POST",
            url=f"{self._base_url}/mixed_people/search",
            provider="apollo-people",
            operation="search_people",
            timeout_seconds=request.timeout_seconds or self._timeout,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "no-cache",
                "X-Api-Key": self._api_key,
            },
        )
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderValidationError(
                "Apollo returned non-JSON",
                provider="apollo-people",
                operation="search_people",
            ) from exc

        people: list[PersonHit] = []
        for row in data.get("people") or data.get("contacts") or []:
            if not isinstance(row, dict):
                continue
            name = (
                row.get("name")
                or " ".join(
                    p for p in (row.get("first_name"), row.get("last_name")) if p
                ).strip()
            )
            if not name:
                continue
            org = row.get("organization")
            company_name = request.company_name
            if isinstance(org, dict) and org.get("name"):
                company_name = str(org["name"])
            people.append(
                PersonHit(
                    full_name=str(name),
                    title=row.get("title") or row.get("headline"),
                    company_name=company_name,
                    linkedin_url=row.get("linkedin_url"),
                    location=row.get("formatted_address") or row.get("city"),
                    raw={
                        k: str(v)
                        for k, v in row.items()
                        if isinstance(v, (str, int, float))
                    },
                )
            )
        return PeopleSearchResponse(
            people=people[: request.max_results],
            usage=UsageInfo(
                operation="search_people",
                unit_type="credits",
                units=1.0,
                provider="apollo-people",
            ),
        )
