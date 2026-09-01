"""Realtime user events via Redis pub/sub (SSE consumers)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Iterator, Protocol

from pydantic import BaseModel, Field


class UserEventType(StrEnum):
    workflow_progress = "workflow_progress"
    workflow_completed = "workflow_completed"
    workflow_cancelled = "workflow_cancelled"
    jobs_discovered = "jobs_discovered"
    scores_calculated = "scores_calculated"
    research_completed = "research_completed"
    contacts_found = "contacts_found"
    resume_ready = "resume_ready"
    application_state_changed = "application_state_changed"
    human_task_created = "human_task_created"
    email_sent = "email_sent"
    workflow_failed = "workflow_failed"
    notification_created = "notification_created"
    follow_up_due = "follow_up_due"
    interview_scheduled = "interview_scheduled"
    offer_updated = "offer_updated"
    heartbeat = "heartbeat"


class UserEvent(BaseModel):
    type: UserEventType
    user_id: uuid.UUID
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def user_events_channel(user_id: uuid.UUID) -> str:
    return f"career-agent:events:{user_id}"


class EventBus(Protocol):
    def publish(self, channel: str, message: str) -> None: ...

    def subscribe(self, channel: str) -> Iterator[str]: ...


class RedisEventBus:
    """Thin Redis pub/sub adapter (decode_responses client)."""

    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client

    def publish(self, channel: str, message: str) -> None:
        self._redis.publish(channel, message)

    def subscribe(self, channel: str) -> Iterator[str]:
        pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(channel)
        try:
            for item in pubsub.listen():
                if item is None:
                    continue
                if item.get("type") != "message":
                    continue
                data = item.get("data")
                if isinstance(data, bytes):
                    yield data.decode("utf-8")
                elif isinstance(data, str):
                    yield data
        finally:
            pubsub.unsubscribe(channel)
            pubsub.close()


class InMemoryEventBus:
    """Test-friendly bus that records publishes; subscribe yields recorded then blocks."""

    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []
        self._queues: dict[str, list[str]] = {}

    def publish(self, channel: str, message: str) -> None:
        self.published.append((channel, message))
        self._queues.setdefault(channel, []).append(message)

    def subscribe(self, channel: str) -> Iterator[str]:
        for msg in list(self._queues.get(channel, [])):
            yield msg


class UserEventPublisher:
    """Publish tenant-scoped events. Never cross user boundaries."""

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    def publish(
        self,
        user_id: uuid.UUID,
        event_type: UserEventType,
        payload: dict[str, Any] | None = None,
    ) -> UserEvent:
        event = UserEvent(
            type=event_type,
            user_id=user_id,
            payload=payload or {},
        )
        self._bus.publish(
            user_events_channel(user_id),
            event.model_dump_json(),
        )
        return event

    def parse_message(self, raw: str) -> UserEvent:
        data = json.loads(raw)
        return UserEvent.model_validate(data)
