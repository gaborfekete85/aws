"""The Bookings DynamoDB table (single-table design).

| Item        | PK           | SK             | GSI1 (by Attendee)    | GSI2 (by Event)    |
|-------------|--------------|----------------|-----------------------|--------------------|
| EventPlaces | EVENT#<id>   | PLACES         |                       |                    |
| Hold        | EVENT#<id>   | HOLD#<booking> |                       |                    |
| Booking     | BOOKING#<id> | BOOKING        | ATTENDEE#<sub>/<ts>   | EVENT#<id>/<ts>    |

Holds are also in the sparse GSI3 (``HOLD`` / logical expiry) that the expiry sweep
queries, and carry a TTL attribute (``expires_at`` = expiry + 24 h) purely for
garbage collection. Keep
``table_definition()`` in sync with ``infra/modules/stack/booking.tf``.
"""

from __future__ import annotations

import os
from functools import cache
from typing import Any

import boto3

PK = "pk"
SK = "sk"
GSI1 = "gsi1"
GSI2 = "gsi2"
GSI3 = "gsi3"  # sparse: only Hold items, sorted by logical expiry (for the sweep)
TTL_ATTRIBUTE = "expires_at"
HOLDS_GSI_PK = "HOLD"
TTL_GRACE_SECONDS = 24 * 3600  # TTL only garbage-collects; the sweep releases Places


def event_pk(event_id: str) -> str:
    return f"EVENT#{event_id}"


def booking_pk(booking_id: str) -> str:
    return f"BOOKING#{booking_id}"


def hold_sk(booking_id: str) -> str:
    return f"HOLD#{booking_id}"


def attendee_gsi(attendee_id: str) -> str:
    return f"ATTENDEE#{attendee_id}"


PLACES_SK = "PLACES"
BOOKING_SK = "BOOKING"


def table_name() -> str:
    return os.environ["BOOKINGS_TABLE"]


@cache
def client() -> Any:
    endpoint = os.environ.get("DYNAMODB_ENDPOINT_URL") or None
    return boto3.client("dynamodb", endpoint_url=endpoint)


def table_definition(name: str) -> dict[str, Any]:
    """CreateTable arguments, mirrored in Terraform (tests create the table from this)."""
    return {
        "TableName": name,
        "BillingMode": "PAY_PER_REQUEST",
        "AttributeDefinitions": [
            {"AttributeName": a, "AttributeType": "S"}
            for a in (
                PK,
                SK,
                f"{GSI1}pk",
                f"{GSI1}sk",
                f"{GSI2}pk",
                f"{GSI2}sk",
                f"{GSI3}pk",
                f"{GSI3}sk",
            )
        ],
        "KeySchema": [
            {"AttributeName": PK, "KeyType": "HASH"},
            {"AttributeName": SK, "KeyType": "RANGE"},
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": index,
                "KeySchema": [
                    {"AttributeName": f"{index}pk", "KeyType": "HASH"},
                    {"AttributeName": f"{index}sk", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
            for index in (GSI1, GSI2, GSI3)
        ],
        "StreamSpecification": {"StreamEnabled": True, "StreamViewType": "NEW_AND_OLD_IMAGES"},
    }
