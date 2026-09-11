"""NotionProvider — optional export only; never a source of truth."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from packages.providers.base import MockBehavior, ProviderMetadata, TimeoutMixin, UsageInfo
from packages.providers.exceptions import ProviderNotConfiguredError

logger = logging.getLogger("career.notion")


class NotionExportKind(str, Enum):
    jobs = "jobs"
    applications = "applications"
    contacts = "contacts"
    interviews = "interviews"


class NotionExportRequest(TimeoutMixin):
    kind: NotionExportKind
    user_id: UUID
    items: list[dict[str, Any]] = Field(default_factory=list)
    database_id: str | None = None


class NotionExportResponse(BaseModel):
    exported: int
    skipped: int = 0
    disconnected: bool = False
    usage: UsageInfo


class NotionProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError

    @abstractmethod
    def export_rows(self, request: NotionExportRequest) -> NotionExportResponse:
        raise NotImplementedError

    @abstractmethod
    def is_connected(self) -> bool:
        raise NotImplementedError


class MockNotionProvider(NotionProvider):
    def __init__(self, *, connected: bool = True) -> None:
        self._connected = connected
        self.exports: list[NotionExportRequest] = []
        self._behavior = MockBehavior(provider_name="mock-notion", latency_ms=2.0)
        self._meta = ProviderMetadata(
            name="mock-notion",
            vendor="mock",
            capabilities=frozenset({"export"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def is_connected(self) -> bool:
        return self._connected

    def export_rows(self, request: NotionExportRequest) -> NotionExportResponse:
        self._behavior.before_call(operation="export", timeout_seconds=request.timeout_seconds)
        if not self._connected:
            return NotionExportResponse(
                exported=0,
                skipped=len(request.items),
                disconnected=True,
                usage=self._behavior.usage(operation="export"),
            )
        self.exports.append(request)
        return NotionExportResponse(
            exported=len(request.items),
            usage=self._behavior.usage(operation="export"),
        )


class StubNotionProvider(NotionProvider):
    """Real Notion API not wired — requires NOTION_API_KEY + HUMAN INPUT for OAuth."""

    def __init__(self, *, api_key: str = "", database_id: str = "") -> None:
        self._api_key = (api_key or "").strip()
        self._database_id = (database_id or "").strip()
        self._meta = ProviderMetadata(
            name="stub-notion",
            vendor="notion",
            capabilities=frozenset({"export"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def is_connected(self) -> bool:
        return bool(self._api_key)

    def export_rows(self, request: NotionExportRequest) -> NotionExportResponse:
        if not self.is_connected():
            logger.info("notion_disconnected_skip_export kind=%s", request.kind.value)
            return NotionExportResponse(
                exported=0,
                skipped=len(request.items),
                disconnected=True,
                usage=UsageInfo(operation="export", provider=self._meta.name),
            )
        raise ProviderNotConfiguredError(
            "Notion live export requires OAuth/database mapping (HUMAN INPUT). "
            "Core product continues without Notion.",
            provider=self._meta.name,
            operation="export",
        )


def create_notion_provider() -> NotionProvider:
    import os

    key = (os.getenv("NOTION_API_KEY") or "").strip()
    if key:
        return StubNotionProvider(
            api_key=key,
            database_id=(os.getenv("NOTION_DATABASE_ID") or "").strip(),
        )
    return MockNotionProvider(connected=False)
