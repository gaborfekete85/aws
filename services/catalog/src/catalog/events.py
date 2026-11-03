"""Domain events the Catalog publishes on the bus (contract with Booking and Notifications)."""

from __future__ import annotations

from typing import Any

from catalog.domain import Event
from localbini_shared.events import DomainEvent, new_event

SERVICE = "catalog"

EVENT_PUBLISHED = "EventPublished"
EVENT_UPDATED = "EventUpdated"
EVENT_CANCELLED = "EventCancelled"


def _snapshot(event: Event) -> dict[str, Any]:
    """Everything consumers need without calling back into the Catalog (ADR-0001)."""
    return {
        "event_id": str(event.id),
        "organizer_id": event.organizer_id,
        "title": event.title,
        "starts_at": event.starts_at.isoformat(),
        "ends_at": event.ends_at.isoformat(),
        "places": event.places,
        "price_cents": event.price.amount_cents,
        "currency": event.price.currency,
        "important_information": event.important_information,
        "location": {
            "name": event.location.name,
            "address": event.location.address,
            "city": event.location.city,
        },
        "status": str(event.status),
    }


def event_published(event: Event) -> DomainEvent:
    return new_event(EVENT_PUBLISHED, _snapshot(event), service=SERVICE)


def event_updated(event: Event, changed: set[str]) -> DomainEvent:
    return new_event(
        EVENT_UPDATED, {**_snapshot(event), "changed": sorted(changed)}, service=SERVICE
    )


def event_cancelled(event: Event) -> DomainEvent:
    data = _snapshot(event)
    data["cancelled_at"] = event.cancelled_at.isoformat() if event.cancelled_at else None
    return new_event(EVENT_CANCELLED, data, service=SERVICE)
