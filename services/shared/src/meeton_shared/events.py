"""Domain-event envelope shared by every service, plus publishing helpers.

Every event on the bus has the same `detail` shape:

    {"event_id", "type", "version", "occurred_at", "source", "correlation_id", "data"}

`DetailType` equals `type` so EventBridge rules can match on it.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

import boto3
from lbz.events.api import EventAPI
from lbz.events.event import Event as LbzEvent

from meeton_shared.logging import current_correlation_id, get_logger

logger = get_logger(__name__)

os.environ.setdefault("EVENTS_BUS_NAME", os.environ.get("EVENT_BUS_NAME", ""))
os.environ.setdefault("AWS_LAMBDA_FUNCTION_NAME", os.environ.get("SERVICE_NAME", "meeton"))

SOURCE_PREFIX = "meeton"


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class DomainEvent:
    type: str
    data: dict[str, Any]
    source: str
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: int = 1
    occurred_at: str = field(default_factory=_now)
    correlation_id: str | None = None

    def to_detail(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_detail(cls, detail: Mapping[str, Any]) -> DomainEvent:
        return cls(
            type=detail["type"],
            data=dict(detail.get("data") or {}),
            source=detail["source"],
            event_id=detail["event_id"],
            version=int(detail.get("version", 1)),
            occurred_at=detail["occurred_at"],
            correlation_id=detail.get("correlation_id"),
        )

    @classmethod
    def from_eventbridge(cls, event: Mapping[str, Any]) -> DomainEvent:
        """Parse an EventBridge event (as delivered to Lambda or via SQS)."""
        detail = event["detail"]
        if isinstance(detail, str):
            detail = json.loads(detail)
        return cls.from_detail(detail)


def service_source(service: str) -> str:
    return f"{SOURCE_PREFIX}.{service}"


def new_event(type_: str, data: dict[str, Any], *, service: str) -> DomainEvent:
    return DomainEvent(
        type=type_,
        data=data,
        source=service_source(service),
        correlation_id=current_correlation_id(),
    )


class _EnvelopeEvent(LbzEvent):
    """lbz Event whose serialized payload is our envelope."""

    def __init__(self, domain_event: DomainEvent) -> None:
        super().__init__(domain_event.to_detail(), event_type=domain_event.type)


def register(domain_event: DomainEvent) -> None:
    """Queue an event on lbz's EventAPI; it is sent only if the HTTP request succeeds."""
    api = EventAPI()
    api.set_source(domain_event.source)
    if bus := os.environ.get("EVENT_BUS_NAME"):
        api.set_bus_name(bus)
    api.register(_EnvelopeEvent(domain_event))


class EventPublisher:
    """Direct publisher for non-HTTP code paths (event handlers, schedulers)."""

    def __init__(self, bus_name: str | None = None, client: Any | None = None) -> None:
        self.bus_name = bus_name or os.environ["EVENT_BUS_NAME"]
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = boto3.client("events")
        return self._client

    def publish(self, events: Iterable[DomainEvent]) -> list[DomainEvent]:
        """Publish events in batches of 10; returns the events that failed."""
        pending = list(events)
        failed: list[DomainEvent] = []
        for start in range(0, len(pending), 10):
            batch = pending[start : start + 10]
            response = self.client.put_events(
                Entries=[
                    {
                        "EventBusName": self.bus_name,
                        "Source": e.source,
                        "DetailType": e.type,
                        "Detail": json.dumps(e.to_detail(), default=str),
                    }
                    for e in batch
                ]
            )
            for event, entry in zip(batch, response["Entries"], strict=True):
                if entry.get("ErrorCode"):
                    logger.error(
                        "event publish failed",
                        extra={"event_type": event.type, "error": entry["ErrorCode"]},
                    )
                    failed.append(event)
        if failed:
            raise PublishError(failed)
        return failed


class PublishError(Exception):
    def __init__(self, failed: list[DomainEvent]) -> None:
        super().__init__(f"{len(failed)} event(s) failed to publish")
        self.failed = failed
