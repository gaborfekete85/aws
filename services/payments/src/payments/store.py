"""Payments table: one Checkout record per Booking, plus processed Stripe event ids.

| Item      | PK                 | SK       |
|-----------|--------------------|----------|
| Checkout  | BOOKING#<id>       | CHECKOUT |
| Processed | STRIPE_EVENT#<id>  | EVENT    |  (webhook idempotency, #26)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import cache
from typing import Any

import boto3
from botocore.exceptions import ClientError
from localbini_shared.errors import NotFoundError


def table_name() -> str:
    return os.environ["PAYMENTS_TABLE"]


@cache
def client() -> Any:
    return boto3.client("dynamodb", endpoint_url=os.environ.get("DYNAMODB_ENDPOINT_URL") or None)


def table_definition(name: str) -> dict[str, Any]:
    return {
        "TableName": name,
        "BillingMode": "PAY_PER_REQUEST",
        "AttributeDefinitions": [
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
        ],
        "KeySchema": [
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
    }


def _key(booking_id: str) -> dict[str, Any]:
    return {"pk": {"S": f"BOOKING#{booking_id}"}, "sk": {"S": "CHECKOUT"}}


@dataclass(frozen=True)
class CheckoutRecord:
    booking_id: str
    attendee_id: str
    status: str  # creating | open | expired | paid | failed
    session_id: str | None = None
    url: str | None = None
    expires_at: str | None = None


def claim(booking_id: str, attendee_id: str, event_id: str) -> bool:
    """Reserve the right to create this Booking's session; False if already claimed."""
    try:
        client().put_item(
            TableName=table_name(),
            Item={
                **_key(booking_id),
                "booking_id": {"S": booking_id},
                "attendee_id": {"S": attendee_id},
                "event_id": {"S": event_id},
                "status": {"S": "creating"},
            },
            ConditionExpression="attribute_not_exists(pk)",
        )
    except ClientError as error:
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise
    return True


def update(booking_id: str, **fields: str) -> None:
    names = {f"#{k}": k for k in fields}
    values = {f":{k}": {"S": v} for k, v in fields.items()}
    client().update_item(
        TableName=table_name(),
        Key=_key(booking_id),
        UpdateExpression="SET " + ", ".join(f"#{k} = :{k}" for k in fields),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )


def get(booking_id: str) -> CheckoutRecord:
    item = (
        client()
        .get_item(TableName=table_name(), Key=_key(booking_id), ConsistentRead=True)
        .get("Item")
    )
    if item is None:
        raise NotFoundError("No Checkout for this Booking yet")

    def s(name: str) -> str | None:
        return item[name]["S"] if name in item else None

    return CheckoutRecord(
        booking_id=item["booking_id"]["S"],
        attendee_id=item["attendee_id"]["S"],
        status=item["status"]["S"],
        session_id=s("session_id"),
        url=s("url"),
        expires_at=s("expires_at"),
    )


def find(booking_id: str) -> CheckoutRecord | None:
    try:
        return get(booking_id)
    except NotFoundError:
        return None


def mark(booking_id: str, status: str) -> bool:
    """Set the Checkout status only if the record exists; False otherwise."""
    try:
        client().update_item(
            TableName=table_name(),
            Key=_key(booking_id),
            UpdateExpression="SET #s = :s",
            ConditionExpression="attribute_exists(pk)",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": {"S": status}},
        )
    except ClientError as error:
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise
    return True
