"""Email the Attendee when a Booking is confirmed (#31)."""

from __future__ import annotations

import time

from localbini_shared.events import DomainEvent
from localbini_shared.logging import get_logger
from notifications import sender
from notifications.rendering import render

logger = get_logger(__name__)

MARKER_TTL_SECONDS = 90 * 24 * 3600


def on_booking_confirmed(event: DomainEvent) -> None:
    data = event.data
    to = data.get("attendee_email")
    if not to:
        logger.warning("no attendee email; skipping", extra={"booking_id": data["booking_id"]})
        return
    details = data.get("event") or {}
    email = render(
        "booking_confirmed",
        {
            "booking_id": data["booking_id"],
            "places": data["places"],
            "amount_cents": data.get("amount_cents", 0),
            "currency": data.get("currency", ""),
            "event": {
                "title": details.get("title") or data.get("event_title", "your Event"),
                "starts_at": details.get("starts_at"),
                "location": details.get("location") or {},
                "important_information": details.get("important_information", ""),
            },
        },
    )
    key = f"BookingConfirmed#{data['booking_id']}"
    if sender.send_once(key, to, email, int(time.time()) + MARKER_TTL_SECONDS):
        logger.info("confirmation sent", extra={"booking_id": data["booking_id"]})
    else:
        logger.info("confirmation already sent", extra={"booking_id": data["booking_id"]})
