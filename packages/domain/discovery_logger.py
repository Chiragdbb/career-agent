"""Append-only discovery run log for development and test environments."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path


def discovery_log_enabled() -> bool:
    if os.getenv("DISCOVERY_LOG_DISABLED", "").strip().lower() in ("1", "true", "yes"):
        return False
    if os.getenv("DISCOVERY_LOG_FILE", "").strip():
        return True
    env = os.getenv("APP_ENV", "development").strip().lower()
    return env in ("development", "test")


def discovery_log_path() -> Path:
    custom = os.getenv("DISCOVERY_LOG_FILE", "").strip()
    if custom:
        return Path(custom)
    return Path("logs/discovery.log")


class DiscoveryFileLogger:
    """Write structured JSON lines to logs/discovery.log in dev/test."""

    def __init__(self, run_id: uuid.UUID) -> None:
        self._run_id = str(run_id)
        self._enabled = discovery_log_enabled()
        self._path = discovery_log_path()

    @property
    def path(self) -> Path:
        return self._path

    def log(self, event: str, **data: object) -> None:
        if not self._enabled:
            return
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": self._run_id,
            "event": event,
            **data,
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str) + "\n")
