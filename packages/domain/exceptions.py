"""Domain-layer exceptions (HTTP mapping happens at the API boundary)."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for domain errors."""


class AuthenticationError(DomainError):
    """Caller is not authenticated or token is invalid."""


class AuthorizationError(DomainError):
    """Caller is authenticated but not allowed to perform the action."""


class NotFoundError(DomainError):
    """Requested entity does not exist (or is outside the caller's tenant)."""
