"""Scheduled sweep (EventBridge, every minute) that releases expired Holds.

Why a sweep and not DynamoDB TTL + Streams: TTL deletes expired items lazily
("typically within a few days"), far too late for a 15-minute Hold. TTL stays
on Hold items only as garbage collection, set 24 h after the logical expiry so
it can never pre-empt the sweep. See docs/adr/0004-hold-expiry-sweep.md.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from booking import repository
from booking.events import hold_expired
from booking.holds import due_holds, expire_hold
from meeton_shared.events import DomainEvent, EventPublisher
from meeton_shared.logging import configure_logging, get_logger

logger = get_logger(__name__)


def sweep(now: datetime | None = None, publisher: EventPublisher | None = None) -> dict[str, int]:
    now_iso = (now or datetime.now(UTC)).isoformat()
    released = skipped = 0
    events: list[DomainEvent] = []
    for hold in due_holds(now_iso):
        event_id = hold["event_id"]["S"]
        booking_id = hold["booking_id"]["S"]
        places = int(hold["places"]["N"])
        if expire_hold(event_id, booking_id, places, now_iso):
            released += 1
            events.append(hold_expired(repository.get(booking_id)))
            logger.info("hold expired", extra={"booking_id": booking_id, "places": places})
        else:
            skipped += 1  # converted by a payment or released by a parallel sweep
    if events:
        (publisher or EventPublisher()).publish(events)
    return {"released": released, "skipped": skipped}


def handle(event: dict[str, Any], context: Any) -> dict[str, int]:
    configure_logging("booking-expiry")
    result = sweep()
    logger.info("hold sweep finished", extra=result)
    return result
