"""Booking's bus consumers.

Handlers publish their follow-up events synchronously: if the bus rejects them,
the handler raises and Lambda retries; every transition is conditional, so a
retry never applies twice.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from localbini_shared.consumers import make_event_handler
from localbini_shared.events import DomainEvent, EventPublisher

from booking import lifecycle, places


def on_catalog_event(event: DomainEvent) -> None:
    """EventPublished / EventUpdated / EventCancelled all carry a full snapshot."""
    places.apply_snapshot(event.data, event.occurred_at)


def _publishing(
    reaction: Callable[[dict[str, Any]], list[DomainEvent]],
) -> Callable[[DomainEvent], None]:
    def handler(event: DomainEvent) -> None:
        follow_ups = reaction(event.data)
        if follow_ups:
            EventPublisher().publish(follow_ups)

    handler.__name__ = reaction.__name__
    return handler


Handler = Callable[[DomainEvent], None]

HANDLERS: dict[str, list[Handler]] = {
    "EventPublished": [on_catalog_event],
    "EventUpdated": [on_catalog_event],
    # close the counter first, then cancel the Bookings
    "EventCancelled": [on_catalog_event, _publishing(lifecycle.on_event_cancelled)],
    "PaymentSucceeded": [_publishing(lifecycle.on_payment_succeeded)],
    "PaymentFailed": [_publishing(lifecycle.on_payment_failed)],
}

handle = make_event_handler(HANDLERS, "booking-consumer")
