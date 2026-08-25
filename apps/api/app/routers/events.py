"""Authenticated SSE stream of tenant-scoped user events."""

from __future__ import annotations

import json
import time
from typing import Iterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.dependencies import CurrentUserIdDep, RedisDep
from packages.domain.events import (
    RedisEventBus,
    UserEvent,
    UserEventPublisher,
    UserEventType,
    user_events_channel,
)

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/stream")
def stream_events(
    request: Request,
    user_id: CurrentUserIdDep,
    redis_client: RedisDep,
) -> StreamingResponse:
    """SSE endpoint scoped to the authenticated user (Redis pub/sub)."""

    channel = user_events_channel(user_id)
    bus = RedisEventBus(redis_client)
    publisher = UserEventPublisher(bus)

    def event_generator() -> Iterator[str]:
        hello = UserEvent(
            type=UserEventType.heartbeat,
            user_id=user_id,
            payload={"status": "connected"},
        )
        yield _sse(hello.model_dump(mode="json"))

        pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(channel)
        try:
            last_heartbeat = time.monotonic()
            while True:
                # Keep request referenced so frameworks can track the connection.
                _ = request
                message = pubsub.get_message(timeout=1.0)
                if message and message.get("type") == "message":
                    data = message.get("data")
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    if isinstance(data, str):
                        try:
                            event = publisher.parse_message(data)
                            if event.user_id != user_id:
                                continue
                            yield _sse(event.model_dump(mode="json"))
                        except Exception:
                            continue

                now = time.monotonic()
                if now - last_heartbeat >= 15:
                    beat = UserEvent(
                        type=UserEventType.heartbeat,
                        user_id=user_id,
                        payload={},
                    )
                    yield _sse(beat.model_dump(mode="json"))
                    last_heartbeat = now
        finally:
            pubsub.unsubscribe(channel)
            pubsub.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"
