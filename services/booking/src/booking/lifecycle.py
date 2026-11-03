"""Booking reactions to Payments and Catalog events.

- ``PaymentSucceeded`` → the Hold becomes a confirmed Booking (``BookingConfirmed``).
  A payment that arrives after the Hold expired, or for an Event that was
  cancelled meanwhile, is flagged ``needs_attention`` for manual handling
  (refunds are out of scope).
- ``PaymentFailed`` → the Hold is released right away (no need to wait for expiry).
- ``EventCancelled`` → every pending/confirmed Booking of the Event is cancelled,
  and the affected Attendees are published in ``EventBookingsCancelled`` chunks
  for Notifications (ADR-0005).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from botocore.exceptions import ClientError
from localbini_shared.events import DomainEvent
from localbini_shared.logging import get_logger

from booking import places, repository
from booking.domain import Booking, BookingStatus
from booking.events import booking_cancelled, booking_confirmed, event_bookings_cancelled
from booking.holds import HoldGone, convert_hold, expire_hold
from booking.table import BOOKING_SK, booking_pk, client, event_pk, hold_sk, table_name

logger = get_logger(__name__)

ATTENDEES_PER_MESSAGE = 200  # ~150 bytes each: far below EventBridge's 256 KB limit


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _set_status(
    booking_id: str, status: BookingStatus, allowed_from: set[str], **extra: str
) -> bool:
    names = {"#s": "status"}
    values: dict[str, Any] = {":new": {"S": str(status)}}
    allowed = []
    for i, current in enumerate(sorted(allowed_from)):
        values[f":from{i}"] = {"S": current}
        allowed.append(f":from{i}")
    sets = ["#s = :new"]
    for key, value in extra.items():
        names[f"#{key}"] = key
        values[f":{key}"] = {"S": value}
        sets.append(f"#{key} = :{key}")
    try:
        client().update_item(
            TableName=table_name(),
            Key={"pk": {"S": booking_pk(booking_id)}, "sk": {"S": BOOKING_SK}},
            UpdateExpression="SET " + ", ".join(sets),
            ConditionExpression=f"#s IN ({', '.join(allowed)})",
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )
    except ClientError as error:
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise
    return True


def flag_for_attention(booking: Booking, reason: str) -> None:
    _set_status(
        booking.booking_id,
        BookingStatus.NEEDS_ATTENTION,
        {"pending", "expired", "cancelled"},
        attention_reason=reason,
        flagged_at=_now(),
    )
    logger.error(
        "booking needs manual handling",
        extra={"booking_id": booking.booking_id, "reason": reason, "alert": "booking_attention"},
    )


# --- payments ---------------------------------------------------------------------
def on_payment_succeeded(data: dict[str, Any]) -> list[DomainEvent]:
    booking = repository.get(data["booking_id"])
    if booking.status is BookingStatus.CONFIRMED:
        return []  # redelivery
    event = places.find(booking.event_id)
    if event is None or not event.is_open:
        flag_for_attention(booking, "paid_for_cancelled_event")
        return []
    try:
        convert_hold(booking.event_id, booking.booking_id, _now())
    except HoldGone:
        flag_for_attention(booking, "paid_after_hold_expired")
        return []
    confirmed = repository.get(booking.booking_id)
    return [booking_confirmed(confirmed, event.details)]


def on_payment_failed(data: dict[str, Any]) -> list[DomainEvent]:
    booking = repository.get(data["booking_id"])
    if booking.status is not BookingStatus.PENDING:
        return []
    if expire_hold(booking.event_id, booking.booking_id, booking.places, _now()):
        released = repository.get(booking.booking_id)
        return [booking_cancelled(released, reason=data.get("reason", "payment_failed"))]
    return []


# --- catalog ----------------------------------------------------------------------
def _cancel_one(booking: Booking, now: str) -> bool:
    if booking.status is BookingStatus.PENDING:
        # drop the Hold too, so the expiry sweep has nothing left to do
        client().delete_item(
            TableName=table_name(),
            Key={"pk": {"S": event_pk(booking.event_id)}, "sk": {"S": hold_sk(booking.booking_id)}},
        )
    return _set_status(
        booking.booking_id,
        BookingStatus.CANCELLED,
        {"pending", "confirmed"},
        cancelled_at=now,
    )


def on_event_cancelled(data: dict[str, Any]) -> list[DomainEvent]:
    event_id = data["event_id"]
    now = _now()
    affected = [
        b
        for b in repository.list_for_event(event_id)
        if b.status in {BookingStatus.PENDING, BookingStatus.CONFIRMED} and _cancel_one(b, now)
    ]
    if not affected:
        return []
    details = {
        "event_id": event_id,
        "title": data.get("title", ""),
        "starts_at": data.get("starts_at"),
        "location": data.get("location") or {},
    }
    attendees = [
        {
            "booking_id": b.booking_id,
            "attendee_id": b.attendee_id,
            "attendee_email": b.attendee_email,
            "places": b.places,
            "was_confirmed": b.status is BookingStatus.CONFIRMED,
        }
        for b in affected
    ]
    chunks = [
        attendees[i : i + ATTENDEES_PER_MESSAGE]
        for i in range(0, len(attendees), ATTENDEES_PER_MESSAGE)
    ]
    logger.info("bookings cancelled", extra={"event_id": event_id, "count": len(affected)})
    return [
        event_bookings_cancelled(details, chunk, part=i + 1, parts=len(chunks))
        for i, chunk in enumerate(chunks)
    ]
