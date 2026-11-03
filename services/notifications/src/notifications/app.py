"""Lambda entrypoint: event type → notification handler."""

from __future__ import annotations

from notifications.booking_confirmed import on_booking_confirmed
from notifications.event_cancelled import on_event_bookings_cancelled
from notifications.handler import Handler, make_sqs_handler

HANDLERS: dict[str, Handler] = {
    "BookingConfirmed": on_booking_confirmed,
    "EventBookingsCancelled": on_event_bookings_cancelled,
}

handle = make_sqs_handler(HANDLERS)
