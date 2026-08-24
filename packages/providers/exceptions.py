"""Predictable exceptions raised by provider adapters."""

from __future__ import annotations


class ProviderError(Exception):
    """Base error for all provider failures."""

    def __init__(self, message: str, *, provider: str | None = None, operation: str | None = None):
        super().__init__(message)
        self.provider = provider
        self.operation = operation


class ProviderTimeoutError(ProviderError):
    """Raised when a provider call exceeds the configured timeout."""


class ProviderRateLimitError(ProviderError):
    """Raised when a vendor rejects the call due to rate limiting."""


class ProviderAuthError(ProviderError):
    """Raised when credentials are missing, invalid, or unauthorized."""


class ProviderUnavailableError(ProviderError):
    """Raised when the vendor service is unreachable or returns a hard failure."""


class ProviderValidationError(ProviderError):
    """Raised when request/response data fails validation."""


class ProviderNotConfiguredError(ProviderError):
    """Raised when required configuration for a real adapter is missing."""
