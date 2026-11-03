"""Reading and updating Booking items."""

from __future__ import annotations

from typing import Any

from booking.domain import Booking
from booking.table import BOOKING_SK, attendee_gsi, booking_pk, client, event_pk, table_name
from localbini_shared.errors import NotFoundError


def get(booking_id: str) -> Booking:
    item = (
        client()
        .get_item(
            TableName=table_name(),
            Key={"pk": {"S": booking_pk(booking_id)}, "sk": {"S": BOOKING_SK}},
            ConsistentRead=True,
        )
        .get("Item")
    )
    if item is None:
        raise NotFoundError("Booking not found", details={"booking_id": booking_id})
    return Booking.from_item(item)


def _query(index: str, key: str, limit: int | None = None) -> list[Booking]:
    kwargs: dict[str, Any] = {
        "TableName": table_name(),
        "IndexName": index,
        "KeyConditionExpression": f"{index}pk = :k",
        "ExpressionAttributeValues": {":k": {"S": key}},
        "ScanIndexForward": False,  # newest first
    }
    bookings: list[Booking] = []
    while True:
        page = client().query(**kwargs)
        bookings.extend(Booking.from_item(i) for i in page["Items"])
        if limit and len(bookings) >= limit:
            return bookings[:limit]
        if "LastEvaluatedKey" not in page:
            return bookings
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def list_for_attendee(attendee_id: str, limit: int = 100) -> list[Booking]:
    return _query("gsi1", attendee_gsi(attendee_id), limit)


def list_for_event(event_id: str) -> list[Booking]:
    return _query("gsi2", event_pk(event_id))


def save(booking: Booking, *, expected_status: str | None = None) -> None:
    """Overwrite the Booking item; optionally only if it still has ``expected_status``."""
    kwargs: dict[str, Any] = {"TableName": table_name(), "Item": booking.to_item()}
    if expected_status is not None:
        kwargs["ConditionExpression"] = "#s = :expected"
        kwargs["ExpressionAttributeNames"] = {"#s": "status"}
        kwargs["ExpressionAttributeValues"] = {":expected": {"S": expected_status}}
    client().put_item(**kwargs)
