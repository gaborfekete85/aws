"""Booking's bus consumers: keep the EventPlaces projection in sync with the Catalog."""

from __future__ import annotations

from localbini_shared.consumers import make_event_handler
from localbini_shared.events import DomainEvent

from booking import places


def on_catalog_event(event: DomainEvent) -> None:
    """EventPublished / EventUpdated / EventCancelled all carry a full snapshot."""
    places.apply_snapshot(event.data, event.occurred_at)


HANDLERS = {
    "EventPublished": [on_catalog_event],
    "EventUpdated": [on_catalog_event],
    "EventCancelled": [on_catalog_event],
}

handle = make_event_handler(HANDLERS, "booking-consumer")
