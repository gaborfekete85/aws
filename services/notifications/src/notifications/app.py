"""Lambda entrypoint: event type → notification handler."""

from __future__ import annotations

from notifications.booking_confirmed import on_booking_confirmed
from notifications.handler import Handler, make_sqs_handler

HANDLERS: dict[str, Handler] = {
    "BookingConfirmed": on_booking_confirmed,
}

handle = make_sqs_handler(HANDLERS)
