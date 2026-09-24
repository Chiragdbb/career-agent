"""Internal QStash callback routes (signature-verified, not under /api/v1)."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.dependencies import DbSessionDep, DiscoveryTaskClientDep
from packages.domain.exceptions import DomainError
from packages.domain.scheduled_discovery import run_scheduled_discover_for_active_users
from packages.providers.qstash import verify_upstash_signature
from workers.discovery.tasks import _run_discovery, _run_rescrape

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/qstash", tags=["internal-qstash"])


class DiscoverJobsBody(BaseModel):
    user_id: uuid.UUID
    workflow_run_id: uuid.UUID
    max_results: int = Field(default=5, ge=1)


class RescrapeJobBody(BaseModel):
    user_id: uuid.UUID
    workflow_run_id: uuid.UUID
    match_id: uuid.UUID


class ScheduledDiscoverBody(BaseModel):
    max_users: int = Field(default=50, ge=1, le=500)


def _verify_url(request: Request, settings: Settings) -> str:
    """Public callback URL QStash signed (prefer configured base over proxy host)."""
    base = (settings.qstash_callback_base_url or "").rstrip("/")
    if base:
        return f"{base}{request.url.path}"
    return str(request.url)


async def _require_qstash(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> bytes:
    body = await request.body()
    keys = [
        k
        for k in [settings.qstash_current_signing_key, settings.qstash_next_signing_key]
        if k
    ]
    verify_url = _verify_url(request, settings)
    ok = verify_upstash_signature(
        signing_keys=keys,
        signature_header=request.headers.get("Upstash-Signature", ""),
        body=body,
        url=verify_url,
    )
    if not ok:
        logger.warning(
            "qstash_signature_rejected verify_url=%s path=%s",
            verify_url,
            request.url.path,
        )
        raise HTTPException(status_code=401, detail="invalid qstash signature")
    return body


def _parse_body(raw: bytes, model: type[BaseModel]) -> BaseModel:
    try:
        data = json.loads(raw.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="invalid json body") from exc
    try:
        return model.model_validate(data)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/discover-jobs")
def discover_jobs(raw: bytes = Depends(_require_qstash)) -> dict[str, Any]:
    payload = _parse_body(raw, DiscoverJobsBody)
    assert isinstance(payload, DiscoverJobsBody)
    logger.info(
        "qstash_discover_jobs user=%s run=%s max=%s",
        payload.user_id,
        payload.workflow_run_id,
        payload.max_results,
    )
    try:
        result = _run_discovery(
            payload.user_id, payload.workflow_run_id, payload.max_results
        )
    except DomainError as exc:
        logger.info(
            "qstash_discover_jobs_skipped user=%s run=%s reason=%s",
            payload.user_id,
            payload.workflow_run_id,
            exc,
        )
        return {"ok": True, "skipped": True, "reason": str(exc)[:200]}
    except Exception:
        logger.exception(
            "qstash_discover_jobs_failed user=%s run=%s",
            payload.user_id,
            payload.workflow_run_id,
        )
        raise HTTPException(status_code=500, detail="discover_jobs failed") from None
    return {"ok": True, "result": result}


@router.post("/rescrape-job")
def rescrape_job(raw: bytes = Depends(_require_qstash)) -> dict[str, Any]:
    payload = _parse_body(raw, RescrapeJobBody)
    assert isinstance(payload, RescrapeJobBody)
    logger.info(
        "qstash_rescrape_job user=%s run=%s match=%s",
        payload.user_id,
        payload.workflow_run_id,
        payload.match_id,
    )
    try:
        result = _run_rescrape(
            payload.user_id, payload.workflow_run_id, payload.match_id
        )
    except DomainError as exc:
        logger.info(
            "qstash_rescrape_skipped user=%s run=%s match=%s reason=%s",
            payload.user_id,
            payload.workflow_run_id,
            payload.match_id,
            exc,
        )
        return {"ok": True, "skipped": True, "reason": str(exc)[:200]}
    except Exception:
        logger.exception(
            "qstash_rescrape_failed user=%s run=%s match=%s",
            payload.user_id,
            payload.workflow_run_id,
            payload.match_id,
        )
        raise HTTPException(status_code=500, detail="rescrape_job failed") from None
    return {"ok": True, "result": result}


@router.post("/scheduled-discover")
def scheduled_discover(
    session: DbSessionDep,
    task_client: DiscoveryTaskClientDep,
    raw: bytes = Depends(_require_qstash),
) -> dict[str, Any]:
    payload = _parse_body(raw if raw.strip() else b"{}", ScheduledDiscoverBody)
    assert isinstance(payload, ScheduledDiscoverBody)
    logger.info("qstash_scheduled_discover max_users=%s", payload.max_users)
    try:
        result = run_scheduled_discover_for_active_users(
            session, task_client, max_users=payload.max_users
        )
    except Exception:
        logger.exception("qstash_scheduled_discover_failed")
        raise HTTPException(status_code=500, detail="scheduled_discover failed") from None
    return {"ok": True, "result": result}
