"""Holds: Places set aside while an Attendee is in Checkout (GLOSSARY).

Placing a Hold is one DynamoDB transaction:
1. decrement ``places_left`` **only if** ``places_left >= n`` and the Event is published,
2. write the Hold item (TTL = expiry),
3. write the Booking item.
Either everything happens or nothing does, so concurrent requests can never overbook.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from botocore.exceptions import ClientError
from localbini_shared.errors import ConflictError

from booking.table import PLACES_SK, client, event_pk, hold_sk, table_name


class NotEnoughPlaces(ConflictError):
    """Fewer Places remain than were requested."""


class EventNotOpen(ConflictError):
    """The Event is not Published (anymore)."""


@dataclass(frozen=True)
class HoldRequest:
    booking_id: str
    event_id: str
    attendee_id: str
    places: int
    expires_at: datetime


def hold_item(req: HoldRequest) -> dict[str, Any]:
    return {
        "pk": {"S": event_pk(req.event_id)},
        "sk": {"S": hold_sk(req.booking_id)},
        "booking_id": {"S": req.booking_id},
        "attendee_id": {"S": req.attendee_id},
        "places": {"N": str(req.places)},
        "expires_at": {"N": str(int(req.expires_at.timestamp()))},
    }


def place_hold(req: HoldRequest, booking_item: dict[str, Any], *, with_hold: bool = True) -> None:
    """Atomically take ``req.places`` and record the Hold + Booking, or raise.

    ``with_hold=False`` (free Events) takes the places for good: no Hold to expire.
    """
    if req.places < 1:
        raise ValueError("places must be >= 1")
    hold_put: list[dict[str, Any]] = (
        [
            {
                "Put": {
                    "TableName": table_name(),
                    "Item": hold_item(req),
                    "ConditionExpression": "attribute_not_exists(pk)",
                }
            }
        ]
        if with_hold
        else []
    )
    try:
        client().transact_write_items(
            TransactItems=[
                {
                    "Update": {
                        "TableName": table_name(),
                        "Key": {"pk": {"S": event_pk(req.event_id)}, "sk": {"S": PLACES_SK}},
                        "UpdateExpression": "SET places_left = places_left - :n",
                        "ConditionExpression": "places_left >= :n AND #status = :published",
                        "ExpressionAttributeNames": {"#status": "status"},
                        "ExpressionAttributeValues": {
                            ":n": {"N": str(req.places)},
                            ":published": {"S": "published"},
                        },
                    }
                },
                *hold_put,
                {
                    "Put": {
                        "TableName": table_name(),
                        "Item": booking_item,
                        "ConditionExpression": "attribute_not_exists(pk)",
                    }
                },
            ]
        )
    except ClientError as error:
        if error.response["Error"]["Code"] != "TransactionCanceledException":
            raise
        reasons = error.response.get("CancellationReasons") or []
        first = reasons[0].get("Code") if reasons else None
        if first == "ConditionalCheckFailed":
            raise _why_rejected(req) from error
        raise


def _why_rejected(req: HoldRequest) -> ConflictError:
    from booking import places

    current = places.find(req.event_id)
    if current is None or not current.is_open:
        return EventNotOpen("This Event is not open for Booking")
    return NotEnoughPlaces(
        f"Only {current.places_left} place(s) left",
        details={"places_left": current.places_left, "requested": req.places},
    )


def release_places(event_id: str, booking_id: str, places: int) -> bool:
    """Return a Hold's Places to the counter exactly once.

    Deleting the Hold item is the guard: if it is already gone (released, expired
    or converted), nothing is returned twice. Returns True if Places were released.
    """
    try:
        client().transact_write_items(
            TransactItems=[
                {
                    "Delete": {
                        "TableName": table_name(),
                        "Key": {"pk": {"S": event_pk(event_id)}, "sk": {"S": hold_sk(booking_id)}},
                        "ConditionExpression": "attribute_exists(pk)",
                    }
                },
                {
                    "Update": {
                        "TableName": table_name(),
                        "Key": {"pk": {"S": event_pk(event_id)}, "sk": {"S": PLACES_SK}},
                        "UpdateExpression": "SET places_left = places_left + :n",
                        "ExpressionAttributeValues": {":n": {"N": str(places)}},
                    }
                },
            ]
        )
    except ClientError as error:
        if error.response["Error"]["Code"] == "TransactionCanceledException":
            return False
        raise
    return True
