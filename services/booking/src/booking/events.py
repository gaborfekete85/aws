"""Domain events the Booking context publishes."""

from __future__ import annotations

from typing import Any

from booking.domain import Booking
from meeton_shared.events import DomainEvent, new_event

SERVICE = "booking"
BOOKING_REQUESTED = "BookingRequested"
BOOKING_CONFIRMED = "BookingConfirmed"
BOOKING_CANCELLED = "BookingCancelled"
HOLD_EXPIRED = "HoldExpired"
EVENT_BOOKINGS_CANCELLED = "EventBookingsCancelled"


def _base(booking: Booking) -> dict[str, Any]:
    return {
        "booking_id": booking.booking_id,
        "event_id": booking.event_id,
        "attendee_id": booking.attendee_id,
        "attendee_email": booking.attendee_email,
        "places": booking.places,
        "amount_cents": booking.amount_cents,
        "currency": booking.currency,
        "event_title": booking.event_title,
    }


def booking_requested(booking: Booking) -> DomainEvent:
    data = _base(booking)
    data["hold_expires_at"] = (
        booking.hold_expires_at.isoformat() if booking.hold_expires_at else None
    )
    return new_event(BOOKING_REQUESTED, data, service=SERVICE)


def booking_confirmed(booking: Booking, event_details: dict[str, Any]) -> DomainEvent:
    data = _base(booking)
    data["event"] = event_details  # title, date, Location, Important information for the email
    return new_event(BOOKING_CONFIRMED, data, service=SERVICE)


def booking_cancelled(booking: Booking, reason: str) -> DomainEvent:
    return new_event(BOOKING_CANCELLED, {**_base(booking), "reason": reason}, service=SERVICE)


def hold_expired(booking: Booking) -> DomainEvent:
    return new_event(HOLD_EXPIRED, _base(booking), service=SERVICE)


def event_bookings_cancelled(
    event: dict[str, Any], attendees: list[dict[str, Any]], *, part: int, parts: int
) -> DomainEvent:
    """Affected Attendees of a cancelled Event, for Notifications (ADR-0005)."""
    return new_event(
        EVENT_BOOKINGS_CANCELLED,
        {"event": event, "attendees": attendees, "part": part, "parts": parts},
        service=SERVICE,
    )
