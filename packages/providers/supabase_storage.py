"""Supabase Storage adapter implementing StorageProvider.

Uses the Storage REST API with the service role key for private buckets.
Object reads for clients should use signed URLs — no JWT secret required.
"""

from __future__ import annotations

import time
from urllib.parse import quote

import httpx

from packages.providers.base import ProviderMetadata, UsageInfo
from packages.providers.exceptions import (
    ProviderAuthError,
    ProviderError,
    ProviderNotConfiguredError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from packages.providers.storage import (
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


class SupabaseStorageProvider(StorageProvider):
    """Real Supabase Storage adapter (private bucket + signed URLs)."""

    def __init__(
        self,
        *,
        supabase_url: str,
        service_role_key: str,
        timeout_seconds: float = 30.0,
    ) -> None:
        base = (supabase_url or "").strip().rstrip("/")
        key = (service_role_key or "").strip()
        if not base:
            raise ProviderNotConfiguredError(
                "SUPABASE_URL is required for Supabase Storage",
                provider="supabase-storage",
            )
        if not key:
            raise ProviderNotConfiguredError(
                "SUPABASE_SERVICE_ROLE_KEY is required for Supabase Storage",
                provider="supabase-storage",
            )
        self._base_url = base
        self._service_role_key = key
        self._default_timeout = timeout_seconds
        self._meta = ProviderMetadata(
            name="supabase-storage",
            vendor="supabase",
            capabilities=frozenset({"put", "get", "delete", "signed_url"}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._meta

    def put_object(self, request: StoragePutRequest) -> StorageObjectResponse:
        started = time.perf_counter()
        url = (
            f"{self._base_url}/storage/v1/object/"
            f"{quote(request.bucket, safe='')}/{_encode_key(request.key)}"
        )
        response = self._request(
            "POST",
            url,
            operation="put_object",
            timeout_seconds=request.timeout_seconds,
            content=request.data,
            headers={
                "Content-Type": request.content_type or "application/octet-stream",
                "x-upsert": "true",
            },
        )
        if response.status_code not in {200, 201}:
            self._raise_for_status(response, operation="put_object")
        return StorageObjectResponse(
            bucket=request.bucket,
            key=request.key,
            size_bytes=len(request.data),
            content_type=request.content_type,
            usage=self._usage(
                operation="put_object",
                unit_type="bytes",
                units=float(len(request.data)),
                started=started,
            ),
        )

    def get_object(self, request: StorageGetRequest) -> StorageGetResponse:
        started = time.perf_counter()
        url = (
            f"{self._base_url}/storage/v1/object/"
            f"{quote(request.bucket, safe='')}/{_encode_key(request.key)}"
        )
        response = self._request(
            "GET",
            url,
            operation="get_object",
            timeout_seconds=request.timeout_seconds,
        )
        if response.status_code == 404:
            raise ProviderValidationError(
                f"object not found: {request.bucket}/{request.key}",
                provider="supabase-storage",
                operation="get_object",
            )
        if response.status_code != 200:
            self._raise_for_status(response, operation="get_object")
        content_type = response.headers.get("content-type")
        return StorageGetResponse(
            bucket=request.bucket,
            key=request.key,
            data=response.content,
            content_type=content_type,
            usage=self._usage(
                operation="get_object",
                unit_type="bytes",
                units=float(len(response.content)),
                started=started,
            ),
        )

    def delete_object(self, request: StorageDeleteRequest) -> StorageDeleteResponse:
        started = time.perf_counter()
        url = f"{self._base_url}/storage/v1/object/{quote(request.bucket, safe='')}"
        response = self._request(
            "DELETE",
            url,
            operation="delete_object",
            timeout_seconds=request.timeout_seconds,
            json={"prefixes": [request.key]},
        )
        if response.status_code not in {200, 204}:
            self._raise_for_status(response, operation="delete_object")
        return StorageDeleteResponse(
            deleted=True,
            usage=self._usage(
                operation="delete_object",
                unit_type="requests",
                units=1.0,
                started=started,
            ),
        )

    def create_signed_url(self, request: StorageSignedUrlRequest) -> StorageSignedUrlResponse:
        started = time.perf_counter()
        url = (
            f"{self._base_url}/storage/v1/object/sign/"
            f"{quote(request.bucket, safe='')}/{_encode_key(request.key)}"
        )
        response = self._request(
            "POST",
            url,
            operation="create_signed_url",
            timeout_seconds=request.timeout_seconds,
            json={"expiresIn": request.expires_in_seconds},
        )
        if response.status_code != 200:
            self._raise_for_status(response, operation="create_signed_url")
        payload = response.json()
        signed_path = payload.get("signedURL") or payload.get("signedUrl") or ""
        if not signed_path:
            raise ProviderValidationError(
                "Supabase Storage signed URL response missing signedURL",
                provider="supabase-storage",
                operation="create_signed_url",
            )
        if signed_path.startswith("http"):
            full_url = signed_path
        else:
            full_url = f"{self._base_url}/storage/v1{signed_path}"
        return StorageSignedUrlResponse(
            url=full_url,
            expires_in_seconds=request.expires_in_seconds,
            usage=self._usage(
                operation="create_signed_url",
                unit_type="requests",
                units=1.0,
                started=started,
            ),
        )

    def _request(
        self,
        method: str,
        url: str,
        *,
        operation: str,
        timeout_seconds: float,
        content: bytes | None = None,
        json: dict | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        req_headers = {
            "Authorization": f"Bearer {self._service_role_key}",
            "apikey": self._service_role_key,
        }
        if headers:
            req_headers.update(headers)
        timeout = timeout_seconds or self._default_timeout
        try:
            with httpx.Client(timeout=timeout) as client:
                return client.request(
                    method,
                    url,
                    content=content,
                    json=json,
                    headers=req_headers,
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                f"supabase-storage timed out after {timeout}s",
                provider="supabase-storage",
                operation=operation,
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(
                f"supabase-storage request failed: {exc}",
                provider="supabase-storage",
                operation=operation,
            ) from exc

    def _raise_for_status(self, response: httpx.Response, *, operation: str) -> None:
        detail = response.text[:300]
        if response.status_code in {401, 403}:
            raise ProviderAuthError(
                f"supabase-storage auth failed ({response.status_code}): {detail}",
                provider="supabase-storage",
                operation=operation,
            )
        if response.status_code == 404:
            raise ProviderValidationError(
                f"supabase-storage object not found: {detail}",
                provider="supabase-storage",
                operation=operation,
            )
        raise ProviderError(
            f"supabase-storage {operation} failed ({response.status_code}): {detail}",
            provider="supabase-storage",
            operation=operation,
        )

    def _usage(
        self,
        *,
        operation: str,
        unit_type: str,
        units: float,
        started: float,
    ) -> UsageInfo:
        return UsageInfo(
            operation=operation,
            unit_type=unit_type,
            units=units,
            estimated_cost_usd=0.0,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            provider="supabase-storage",
        )


def _encode_key(key: str) -> str:
    """Encode object key path segments for URL use."""
    return "/".join(quote(part, safe="") for part in key.split("/") if part != "")
