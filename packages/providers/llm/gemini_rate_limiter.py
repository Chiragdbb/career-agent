"""Redis-backed RPM limiter for Gemini free-tier quota sharing across workers."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Protocol

logger = logging.getLogger("career.providers.gemini")

_REDIS_KEY_PREFIX = "gemini:rpm"
_REDIS_ANALYTICS_PREFIX = "gemini:analytics:rpm"


@dataclass(frozen=True)
class RateLimitSnapshot:
    requests_this_minute: int
    rpm_limit: int
    gemini_tier: str
    minute_bucket: int


class GeminiRateLimiter(Protocol):
    def acquire(self) -> RateLimitSnapshot: ...

    def current_snapshot(self) -> RateLimitSnapshot: ...


def _minute_bucket(now: float | None = None) -> int:
    return int((now or time.time()) // 60)


def _rpm_key(minute: int) -> str:
    return f"{_REDIS_KEY_PREFIX}:{minute}"


def _analytics_key(minute: int) -> str:
    return f"{_REDIS_ANALYTICS_PREFIX}:{minute}"


class RedisGeminiRateLimiter:
    """Distributed fixed-window RPM limiter using Redis INCR."""

    def __init__(
        self,
        redis_client: Any,
        *,
        rpm_limit: int,
        gemini_tier: str = "free",
        sleep_fn: Any = time.sleep,
    ) -> None:
        self._redis = redis_client
        self._rpm_limit = max(1, rpm_limit)
        self._tier = gemini_tier
        self._sleep = sleep_fn

    def current_snapshot(self) -> RateLimitSnapshot:
        minute = _minute_bucket()
        count = int(self._redis.get(_rpm_key(minute)) or 0)
        return RateLimitSnapshot(
            requests_this_minute=count,
            rpm_limit=self._rpm_limit,
            gemini_tier=self._tier,
            minute_bucket=minute,
        )

    def acquire(self) -> RateLimitSnapshot:
        while True:
            now = time.time()
            minute = _minute_bucket(now)
            key = _rpm_key(minute)
            count = int(self._redis.incr(key))
            if count == 1:
                self._redis.expire(key, 120)
            self._redis.set(_analytics_key(minute), count, ex=3600)

            if count <= self._rpm_limit:
                snapshot = RateLimitSnapshot(
                    requests_this_minute=count,
                    rpm_limit=self._rpm_limit,
                    gemini_tier=self._tier,
                    minute_bucket=minute,
                )
                logger.debug(
                    "gemini_rate_limit_acquire rpm=%d/%d tier=%s bucket=%d",
                    count,
                    self._rpm_limit,
                    self._tier,
                    minute,
                )
                return snapshot

            # Over limit — roll back increment and wait for next window slot.
            self._redis.decr(key)
            wait_seconds = ((minute + 1) * 60) - now
            wait_seconds = min(max(wait_seconds, 0.25), 60.0)
            logger.info(
                "gemini_rate_limit_wait rpm=%d/%d tier=%s sleep=%.2fs",
                count - 1,
                self._rpm_limit,
                self._tier,
                wait_seconds,
            )
            self._sleep(wait_seconds)


class InMemoryGeminiRateLimiter:
    """Process-local fallback when Redis is unavailable (single-worker dev)."""

    def __init__(
        self,
        *,
        rpm_limit: int,
        gemini_tier: str = "free",
        sleep_fn: Any = time.sleep,
    ) -> None:
        self._rpm_limit = max(1, rpm_limit)
        self._tier = gemini_tier
        self._sleep = sleep_fn
        self._counts: dict[int, int] = {}

    def current_snapshot(self) -> RateLimitSnapshot:
        minute = _minute_bucket()
        return RateLimitSnapshot(
            requests_this_minute=self._counts.get(minute, 0),
            rpm_limit=self._rpm_limit,
            gemini_tier=self._tier,
            minute_bucket=minute,
        )

    def acquire(self) -> RateLimitSnapshot:
        while True:
            now = time.time()
            minute = _minute_bucket(now)
            count = self._counts.get(minute, 0) + 1
            if count <= self._rpm_limit:
                self._counts[minute] = count
                return RateLimitSnapshot(
                    requests_this_minute=count,
                    rpm_limit=self._rpm_limit,
                    gemini_tier=self._tier,
                    minute_bucket=minute,
                )
            wait_seconds = min(max(((minute + 1) * 60) - now, 0.25), 60.0)
            self._sleep(wait_seconds)
