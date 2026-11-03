"""EventPlaces: Booking's own projection of Catalog Events (Places, price, status).

Built only from bus events (ADR-0001: no cross-store reads). ``places_left`` is
the counter Holds decrement with a conditional write.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from botocore.exceptions import ClientError
from localbini_shared.errors import NotFoundError
from localbini_shared.logging import get_logger

from booking.table import PLACES_SK, client, event_pk, table_name

logger = get_logger(__name__)

MAX_RETRIES = 5


@dataclass(frozen=True)
class EventPlaces:
    event_id: str
    title: str
    places_total: int
    places_left: int
    price_cents: int
    currency: str
    status: str
    starts_at: datetime
    source_updated_at: str

    @property
    def is_free(self) -> bool:
        return self.price_cents == 0

    @property
    def is_open(self) -> bool:
        return self.status == "published"


def _from_item(item: dict[str, Any]) -> EventPlaces:
    return EventPlaces(
        event_id=item["event_id"]["S"],
        title=item.get("title", {}).get("S", ""),
        places_total=int(item["places_total"]["N"]),
        places_left=int(item["places_left"]["N"]),
        price_cents=int(item["price_cents"]["N"]),
        currency=item["currency"]["S"],
        status=item["status"]["S"],
        starts_at=datetime.fromisoformat(item["starts_at"]["S"]),
        source_updated_at=item["source_updated_at"]["S"],
    )


def get(event_id: str, *, consistent: bool = True) -> EventPlaces:
    item = (
        client()
        .get_item(
            TableName=table_name(),
            Key={"pk": {"S": event_pk(event_id)}, "sk": {"S": PLACES_SK}},
            ConsistentRead=consistent,
        )
        .get("Item")
    )
    if item is None:
        raise NotFoundError("Event is not open for Booking", details={"event_id": event_id})
    return _from_item(item)


def find(event_id: str) -> EventPlaces | None:
    try:
        return get(event_id)
    except NotFoundError:
        return None


def apply_snapshot(data: dict[str, Any], occurred_at: str) -> None:
    """Upsert from EventPublished / EventUpdated / EventCancelled.

    Changing ``places`` moves ``places_left`` by the same delta, so places already
    held or booked stay taken. Out-of-order deliveries (older ``occurred_at``) are
    ignored. Uses optimistic locking on ``places_total``.
    """
    event_id = data["event_id"]
    new_total = int(data["places"])
    for _ in range(MAX_RETRIES):
        current = find(event_id)
        if current is not None and current.source_updated_at >= occurred_at:
            logger.info("stale catalog event ignored", extra={"event_id": event_id})
            return
        values = {
            ":title": {"S": data.get("title", "")},
            ":total": {"N": str(new_total)},
            ":price": {"N": str(int(data["price_cents"]))},
            ":currency": {"S": data["currency"]},
            ":status": {"S": data.get("status", "published")},
            ":starts": {"S": data["starts_at"]},
            ":ts": {"S": occurred_at},
            ":event_id": {"S": event_id},
        }
        key = {"pk": {"S": event_pk(event_id)}, "sk": {"S": PLACES_SK}}
        try:
            if current is None:
                values[":left"] = {"N": str(new_total)}
                client().put_item(
                    TableName=table_name(),
                    Item={
                        **key,
                        "event_id": values[":event_id"],
                        "title": values[":title"],
                        "places_total": values[":total"],
                        "places_left": values[":left"],
                        "price_cents": values[":price"],
                        "currency": values[":currency"],
                        "status": values[":status"],
                        "starts_at": values[":starts"],
                        "source_updated_at": values[":ts"],
                    },
                    ConditionExpression="attribute_not_exists(pk)",
                )
            else:
                values[":delta"] = {"N": str(new_total - current.places_total)}
                values[":old_total"] = {"N": str(current.places_total)}
                client().update_item(
                    TableName=table_name(),
                    Key=key,
                    UpdateExpression=(
                        "SET title = :title, places_total = :total,"
                        " places_left = places_left + :delta, price_cents = :price,"
                        " currency = :currency, #status = :status, starts_at = :starts,"
                        " source_updated_at = :ts"
                    ),
                    ConditionExpression="places_total = :old_total AND source_updated_at < :ts",
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={k: v for k, v in values.items() if k != ":event_id"},
                )
            return
        except ClientError as error:
            if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise
            # concurrent writer won; re-read and retry
    raise RuntimeError(f"Could not apply catalog update for {event_id}")
