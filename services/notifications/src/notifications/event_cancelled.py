"""Notify every affected Attendee when an Event is cancelled (#32, ADR-0005).

Consumes ``EventBookingsCancelled`` (Booking lists the affected Attendees) and
sends the emails concurrently with asyncio, bounded by a semaphore and the SES
send rate. Any failed send fails the SQS record; the redelivery skips everyone
already emailed (sent markers), and after 5 attempts the record lands in the DLQ.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from localbini_shared.events import DomainEvent
from localbini_shared.logging import get_logger
from notifications import sender
from notifications.fanout import PartialFailure, RateLimiter, fan_out
from notifications.rendering import render

logger = get_logger(__name__)

MARKER_TTL_SECONDS = 90 * 24 * 3600


def max_concurrency() -> int:
    return int(os.environ.get("SES_MAX_CONCURRENCY", "5"))


def send_rate() -> float:
    return float(os.environ.get("SES_MAX_SEND_RATE", "1"))


def on_event_bookings_cancelled(event: DomainEvent) -> None:
    details = event.data["event"]
    recipients = [a for a in event.data["attendees"] if a.get("attendee_email")]
    expires = int(time.time()) + MARKER_TTL_SECONDS

    def send_one(attendee: dict[str, Any]) -> bool:
        email = render(
            "event_cancelled",
            {
                "event": {
                    "title": details.get("title", "Your Event"),
                    "starts_at": details.get("starts_at"),
                    "location": details.get("location") or {},
                },
                "booking_id": attendee["booking_id"],
                "places": attendee["places"],
                "was_confirmed": attendee.get("was_confirmed", False),
            },
        )
        key = f"EventCancelled#{details['event_id']}#{attendee['booking_id']}"
        return sender.send_once(key, attendee["attendee_email"], email, expires)

    limiter = RateLimiter(rate=send_rate(), burst=max(1, int(send_rate())))
    result = asyncio.run(
        fan_out(recipients, send_one, max_concurrency=max_concurrency(), limiter=limiter)
    )
    logger.info(
        "cancellation emails",
        extra={
            "event_id": details["event_id"],
            "part": event.data.get("part"),
            "sent": result.sent,
            "skipped": result.skipped,
            "failed": len(result.failed),
        },
    )
    if result.failed:
        raise PartialFailure(result)
