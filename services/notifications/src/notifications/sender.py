"""Sending email with SES v2, plus a sent-marker store for idempotency."""

from __future__ import annotations

import os
from functools import cache
from typing import Any

import boto3
from botocore.exceptions import ClientError

from notifications.rendering import Email


@cache
def ses() -> Any:
    return boto3.client("sesv2")


@cache
def dynamodb() -> Any:
    return boto3.client("dynamodb", endpoint_url=os.environ.get("DYNAMODB_ENDPOINT_URL") or None)


def sender_address() -> str:
    return os.environ["SENDER_EMAIL"]


def send(to: str, email: Email) -> str:
    response = ses().send_email(
        FromEmailAddress=f"Localbini <{sender_address()}>",
        Destination={"ToAddresses": [to]},
        Content={
            "Simple": {
                "Subject": {"Data": email.subject, "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": email.html, "Charset": "UTF-8"},
                    "Text": {"Data": email.text, "Charset": "UTF-8"},
                },
            }
        },
        EmailTags=[{"Name": "app", "Value": "localbini"}],
    )
    message_id: str = response["MessageId"]
    return message_id


# --- idempotency ------------------------------------------------------------------
def table_name() -> str:
    return os.environ["NOTIFICATIONS_TABLE"]


def table_definition(name: str) -> dict[str, Any]:
    return {
        "TableName": name,
        "BillingMode": "PAY_PER_REQUEST",
        "AttributeDefinitions": [{"AttributeName": "pk", "AttributeType": "S"}],
        "KeySchema": [{"AttributeName": "pk", "KeyType": "HASH"}],
    }


def claim(key: str, expires_at_epoch: int) -> bool:
    """Reserve ``key`` (e.g. ``BookingConfirmed#<booking>``); False if already sent."""
    try:
        dynamodb().put_item(
            TableName=table_name(),
            Item={"pk": {"S": key}, "expires_at": {"N": str(expires_at_epoch)}},
            ConditionExpression="attribute_not_exists(pk)",
        )
    except ClientError as error:
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise
    return True


def release(key: str) -> None:
    """Sending failed: forget the claim so a retry sends it."""
    dynamodb().delete_item(TableName=table_name(), Key={"pk": {"S": key}})


def send_once(key: str, to: str, email: Email, expires_at_epoch: int) -> bool:
    """Send unless already sent; returns True if an email went out now."""
    if not claim(key, expires_at_epoch):
        return False
    try:
        send(to, email)
    except Exception:
        release(key)
        raise
    return True
