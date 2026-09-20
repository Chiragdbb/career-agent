"""Per-run discovery/rescrape observability (JSONL + summary + stdout)."""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_stdout = logging.getLogger("career.discovery.run")
_warned_legacy_file = False

_STDOUT_EVENTS = frozenset(
    {
        "run_started",
        "queries_planned",
        "search_result",
        "search_failed",
        "scrape_result",
        "scrape_failed",
        "llm_result",
        "llm_failed",
        "job_created",
        "job_duplicate",
        "job_updated",
        "ingest_failed",
        "run_completed",
        "run_failed",
        "run_cancelled",
    }
)


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes")


def discovery_log_enabled() -> bool:
    if _truthy(os.getenv("DISCOVERY_LOG_DISABLED")):
        return False
    if "DISCOVERY_LOG_DIR" in os.environ:
        return True
    env = os.getenv("APP_ENV", "development").strip().lower()
    return env in ("development", "test")


def discovery_log_dir() -> Path:
    custom = os.getenv("DISCOVERY_LOG_DIR", "").strip()
    if custom:
        return Path(custom)
    return Path("logs/discovery")


def discovery_log_bodies_enabled() -> bool:
    return _truthy(os.getenv("DISCOVERY_LOG_BODIES"))


def discovery_log_snippet_chars() -> int:
    raw = (os.getenv("DISCOVERY_LOG_SNIPPET_CHARS") or "500").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 500


def _warn_legacy_log_file() -> None:
    global _warned_legacy_file
    if _warned_legacy_file:
        return
    if os.getenv("DISCOVERY_LOG_FILE", "").strip():
        _stdout.warning(
            "DISCOVERY_LOG_FILE is ignored; use DISCOVERY_LOG_DIR for per-run folders"
        )
        _warned_legacy_file = True


class DiscoveryRunLogger:
    """Write structured JSON lines and a final summary under logs/discovery/<run_id>/."""

    def __init__(
        self,
        run_id: uuid.UUID,
        *,
        workflow_type: str = "job_discovery",
    ) -> None:
        _warn_legacy_log_file()
        self._run_id = str(run_id)
        self._workflow_type = workflow_type
        self._enabled = discovery_log_enabled()
        self._bodies = discovery_log_bodies_enabled()
        self._snippet_chars = discovery_log_snippet_chars()
        self._run_dir = discovery_log_dir() / self._run_id
        self._events_path = self._run_dir / "events.jsonl"
        self._summary_path = self._run_dir / "summary.json"
        self._started_at = datetime.now(timezone.utc)
        self.counts: dict[str, int] = {
            "search_calls": 0,
            "urls_found": 0,
            "urls_skipped": 0,
            "scrapes": 0,
            "scrape_failures": 0,
            "extracts": 0,
            "created": 0,
            "duplicates": 0,
            "skipped_invalid": 0,
        }
        self.queries: list[str] = []
        self.config: dict[str, Any] = {}
        self.errors: list[str] = []
        self.knobs_touched: list[str] = []

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def run_dir(self) -> Path:
        return self._run_dir

    @property
    def events_path(self) -> Path:
        return self._events_path

    @property
    def summary_path(self) -> Path:
        return self._summary_path

    @property
    def bodies_enabled(self) -> bool:
        return self._bodies

    @property
    def snippet_chars(self) -> int:
        return self._snippet_chars

    def snippet(self, text: str | None) -> str | None:
        if text is None:
            return None
        limit = self._snippet_chars
        if limit <= 0:
            return ""
        if len(text) <= limit:
            return text
        return text[:limit]

    def payload_fields(
        self,
        *,
        text: str | None,
        snippet_key: str,
        body_key: str,
    ) -> dict[str, Any]:
        """Attach length + snippet, and full body when DISCOVERY_LOG_BODIES is on."""
        value = text or ""
        fields: dict[str, Any] = {
            f"{snippet_key}_chars": len(value),
            snippet_key: self.snippet(value),
        }
        if self._bodies:
            fields[body_key] = value
        return fields

    def bump(self, key: str, amount: int = 1) -> None:
        if key in self.counts:
            self.counts[key] += amount

    def log(self, event: str, **data: object) -> None:
        if not self._enabled:
            return
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": self._run_id,
            "workflow_type": self._workflow_type,
            "event": event,
            **data,
        }
        self._run_dir.mkdir(parents=True, exist_ok=True)
        with self._events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str) + "\n")
        if event in _STDOUT_EVENTS:
            self._mirror_stdout(event, data)

    def _mirror_stdout(self, event: str, data: dict[str, object]) -> None:
        parts = [f"{self._workflow_type} run={self._run_id} {event}"]
        for key in (
            "query",
            "url",
            "provider",
            "operation",
            "content_source",
            "chars",
            "hits",
            "accepted",
            "tokens_in",
            "tokens_out",
            "title",
            "company",
            "error",
            "created",
            "duplicates",
            "skipped",
            "status",
        ):
            if key in data and data[key] is not None:
                parts.append(f"{key}={data[key]!r}" if isinstance(data[key], str) else f"{key}={data[key]}")
        _stdout.info(" ".join(parts))

    def write_summary(
        self,
        *,
        status: str,
        usage: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        if not self._enabled:
            return
        duration_ms = int(
            (datetime.now(timezone.utc) - self._started_at).total_seconds() * 1000
        )
        summary: dict[str, Any] = {
            "run_id": self._run_id,
            "workflow_type": self._workflow_type,
            "status": status,
            "duration_ms": duration_ms,
            "config": self.config,
            "queries": list(self.queries),
            "counts": dict(self.counts),
            "usage": usage or {"by_provider": {}, "quota": {}},
            "errors": list(self.errors),
            "knobs_touched": list(self.knobs_touched),
        }
        if extra:
            summary.update(extra)
        self._run_dir.mkdir(parents=True, exist_ok=True)
        self._summary_path.write_text(
            json.dumps(summary, indent=2, default=str) + "\n",
            encoding="utf-8",
        )


# Back-compat alias for any external imports during transition.
DiscoveryFileLogger = DiscoveryRunLogger
