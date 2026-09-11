"""Optional Sentry integration — stub when SENTRY_DSN is absent."""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("career.sentry")

_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "api_key",
        "apikey",
        "authorization",
        "token",
        "oauth",
        "secret",
        "resume",
        "email_body",
        "body_html",
    }
)

ERROR_CLASSES = frozenset(
    {
        "provider_error",
        "validation_error",
        "browser_error",
        "human_required",
        "configuration_error",
        "internal_error",
    }
)


def sentry_enabled() -> bool:
    return bool((os.getenv("SENTRY_DSN") or "").strip())


def init_sentry(*, service: str = "api") -> bool:
    """Initialize Sentry SDK when DSN is present. Returns True if active."""
    dsn = (os.getenv("SENTRY_DSN") or "").strip()
    if not dsn:
        logger.info("sentry_disabled service=%s reason=no_dsn", service)
        return False
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=dsn,
            environment=os.getenv("APP_ENV", "development"),
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE") or "0.0"),
            send_default_pii=False,
        )
        sentry_sdk.set_tag("service", service)
        logger.info("sentry_enabled service=%s", service)
        return True
    except Exception:
        logger.warning("sentry_init_failed", exc_info=True)
        return False


def capture_exception(
    exc: BaseException,
    *,
    error_class: str = "internal_error",
    user_id: str | None = None,
    workflow_id: str | None = None,
    task_id: str | None = None,
    job_id: str | None = None,
    application_id: str | None = None,
    provider: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    if error_class not in ERROR_CLASSES:
        error_class = "internal_error"
    context = _scrub(
        {
            "error_class": error_class,
            "user_id": user_id,
            "workflow_id": workflow_id,
            "task_id": task_id,
            "job_id": job_id,
            "application_id": application_id,
            "provider": provider,
            **(extra or {}),
        }
    )
    if not sentry_enabled():
        logger.debug("sentry_stub_capture class=%s ctx=%s", error_class, context)
        return
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            scope.set_tag("error_class", error_class)
            for key, value in context.items():
                if value is not None:
                    scope.set_extra(key, value)
            sentry_sdk.capture_exception(exc)
    except Exception:
        logger.warning("sentry_capture_failed", exc_info=True)


def _scrub(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in payload.items():
        lower = key.lower()
        if any(s in lower for s in _SENSITIVE_KEYS):
            cleaned[key] = "[redacted]"
        else:
            cleaned[key] = value
    return cleaned
