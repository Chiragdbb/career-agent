"""Ops helper: bulk-cancel pending QStash messages (production task queue)."""

from __future__ import annotations

import os
import sys

import httpx

from packages.providers.qstash import cancel_all_messages
from packages.shared.env import load_project_env


def main() -> int:
    load_project_env()
    token = (os.getenv("QSTASH_TOKEN") or "").strip().strip('"')
    if not token:
        print("no QSTASH_TOKEN", file=sys.stderr)
        return 1

    # Best-effort peek (endpoint may 405 depending on account/API version).
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=30.0) as client:
        listed = client.get("https://qstash.upstash.io/v2/messages", headers=headers)
        print("list_status", listed.status_code)

    cancelled = cancel_all_messages(token=token)
    print("cancelled", cancelled)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
