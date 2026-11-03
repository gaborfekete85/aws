"""Application service: an Attendee requests a Booking."""

from __future__ import annotations

import os
from datetime import UTC, datetime

from booking import places, repository
from booking.domain import Booking, BookingStatus
from booking.events import booking_confirmed, booking_requested
from booking.holds import EventNotOpen, HoldRequest, place_hold
from meeton_shared.auth import Principal, require_authenticated
from meeton_shared.errors import ForbiddenError
from meeton_shared.events import DomainEvent


def hold_minutes() -> int:
    return int(os.environ.get("HOLD_MINUTES", "15"))


def request_booking(
    principal: Principal, event_id: str, n_places: int, now: datetime | None = None
) -> tuple[Booking, list[DomainEvent]]:
    attendee_id = require_authenticated(principal)
    now = now or datetime.now(UTC)
    event = places.get(event_id)
    if not event.is_open:
        raise EventNotOpen("This Event is not open for Booking")
    if event.starts_at <= now:
        raise EventNotOpen("This Event has already started")

    booking = Booking.request(
        event_id=event_id,
        attendee_id=attendee_id,
        attendee_email=principal.email,
        places=n_places,
        unit_price_cents=event.price_cents,
        currency=event.currency,
        hold_minutes=hold_minutes(),
        event_title=event.title,
        now=now,
    )
    request = HoldRequest(
        booking.booking_id, event_id, attendee_id, n_places, booking.hold_expires_at or now
    )
    if booking.is_free:
        booking.confirm(now)
        booking.hold_expires_at = None
        place_hold(request, booking.to_item(), with_hold=False)
        return booking, [booking_confirmed(booking, event.details)]

    place_hold(request, booking.to_item())
    return booking, [booking_requested(booking)]


def get_booking(principal: Principal, booking_id: str) -> Booking:
    require_authenticated(principal)
    booking = repository.get(booking_id)
    if booking.attendee_id != principal.user_id and not principal.is_admin:
        raise ForbiddenError("This is not your Booking")
    return booking


def my_bookings(principal: Principal) -> list[Booking]:
    return repository.list_for_attendee(require_authenticated(principal))


def availability(event_id: str) -> dict[str, object]:
    event = places.get(event_id, consistent=False)
    return {
        "event_id": event_id,
        "places_total": event.places_total,
        "places_left": max(event.places_left, 0),
        "price_cents": event.price_cents,
        "currency": event.currency,
        "open": event.is_open,
    }


__all__ = ["BookingStatus", "availability", "get_booking", "my_bookings", "request_booking"]
