"""StorageProvider — object storage for resumes and documents.

Product default: Supabase Storage via `SupabaseStorageProvider`
(private buckets + signed URLs; no JWT secret required in .env for that flow).
Do not add AWS S3 adapters in this step.
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
from packages.providers.exceptions import ProviderValidationError


class StoragePutRequest(TimeoutMixin):
    bucket: str = Field(min_length=1)
    key: str = Field(min_length=1)
    data: bytes
    content_type: str = "application/octet-stream"


class StorageGetRequest(TimeoutMixin):
    bucket: str = Field(min_length=1)
    key: str = Field(min_length=1)


class StorageDeleteRequest(TimeoutMixin):
    bucket: str = Field(min_length=1)
    key: str = Field(min_length=1)


class StorageSignedUrlRequest(TimeoutMixin):
    bucket: str = Field(min_length=1)
    key: str = Field(min_length=1)
    expires_in_seconds: int = Field(default=3600, ge=1, le=86400)


class StorageObjectResponse(BaseModel):
    bucket: str
    key: str
    size_bytes: int
    content_type: str | None = None
    usage: UsageInfo


class StorageGetResponse(BaseModel):
    bucket: str
    key: str
    data: bytes
    content_type: str | None = None
    usage: UsageInfo


class StorageSignedUrlResponse(BaseModel):
    url: HttpUrl | str
    expires_in_seconds: int
    usage: UsageInfo


class StorageDeleteResponse(BaseModel):
    deleted: bool
    usage: UsageInfo


class StorageProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError

    @abstractmethod
    def put_object(self, request: StoragePutRequest) -> StorageObjectResponse:
        raise NotImplementedError

    @abstractmethod
    def get_object(self, request: StorageGetRequest) -> StorageGetResponse:
        raise NotImplementedError

    @abstractmethod
    def delete_object(self, request: StorageDeleteRequest) -> StorageDeleteResponse:
        raise NotImplementedError

    @abstractmethod
    def create_signed_url(self, request: StorageSignedUrlRequest) -> StorageSignedUrlResponse:
        raise NotImplementedError


class MockStorageProvider(StorageProvider):
    def __init__(
        self,
        *,
        fail_with: Exception | None = None,
        simulate_timeout: bool = False,
        latency_ms: float = 2.0,
    ) -> None:
        self._objects: dict[tuple[str, str], tuple[bytes, str]] = {}
        self._behavior = MockBehavior(
            fail_with=fail_with,
            simulate_timeout=simulate_timeout,
            latency_ms=latency_ms,
            provider_name="mock-storage",
        )
        self._meta = ProviderMetadata(
            name="mock-storage",
            vendor="mock",
            capabilities=frozenset({"put", "get", "delete", "signed_url"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def put_object(self, request: StoragePutRequest) -> StorageObjectResponse:
        self._behavior.before_call(operation="put_object", timeout_seconds=request.timeout_seconds)
        self._objects[(request.bucket, request.key)] = (request.data, request.content_type)
        return StorageObjectResponse(
            bucket=request.bucket,
            key=request.key,
            size_bytes=len(request.data),
            content_type=request.content_type,
            usage=self._behavior.usage(
                operation="put_object",
                unit_type="bytes",
                units=float(len(request.data)),
            ),
        )

    def get_object(self, request: StorageGetRequest) -> StorageGetResponse:
        self._behavior.before_call(operation="get_object", timeout_seconds=request.timeout_seconds)
        try:
            data, content_type = self._objects[(request.bucket, request.key)]
        except KeyError as exc:
            raise ProviderValidationError(
                f"object not found: {request.bucket}/{request.key}",
                provider="mock-storage",
                operation="get_object",
            ) from exc
        return StorageGetResponse(
            bucket=request.bucket,
            key=request.key,
            data=data,
            content_type=content_type,
            usage=self._behavior.usage(
                operation="get_object",
                unit_type="bytes",
                units=float(len(data)),
            ),
        )

    def delete_object(self, request: StorageDeleteRequest) -> StorageDeleteResponse:
        self._behavior.before_call(operation="delete_object", timeout_seconds=request.timeout_seconds)
        deleted = self._objects.pop((request.bucket, request.key), None) is not None
        return StorageDeleteResponse(
            deleted=deleted,
            usage=self._behavior.usage(operation="delete_object", unit_type="requests", units=1.0),
        )

    def create_signed_url(self, request: StorageSignedUrlRequest) -> StorageSignedUrlResponse:
        self._behavior.before_call(
            operation="create_signed_url",
            timeout_seconds=request.timeout_seconds,
        )
        return StorageSignedUrlResponse(
            url=f"https://storage.example.com/{request.bucket}/{request.key}?sig=mock",
            expires_in_seconds=request.expires_in_seconds,
            usage=self._behavior.usage(operation="create_signed_url", unit_type="requests", units=1.0),
        )
