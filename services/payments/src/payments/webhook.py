"""Stripe webhook → PaymentSucceeded / PaymentFailed on the bus.

- The signature is verified over the **raw** request body; anything invalid is a 400.
- Each Stripe event id is recorded with a conditional write before anything is
  emitted, so Stripe's at-least-once retries never produce duplicate domain events.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import stripe
from botocore.exceptions import ClientError
from localbini_shared.errors import DomainError
from localbini_shared.events import DomainEvent, EventPublisher, new_event
from localbini_shared.logging import get_logger

from payments import store
from payments.gateway import PaymentGateway, StripeGateway

logger = get_logger(__name__)

SERVICE = "payments"
PAYMENT_SUCCEEDED = "PaymentSucceeded"
PAYMENT_FAILED = "PaymentFailed"

SUCCEEDED = {"checkout.session.completed", "checkout.session.async_payment_succeeded"}
FAILED = {"checkout.session.async_payment_failed", "checkout.session.expired"}


class InvalidSignature(DomainError):
    """Unverifiable webhook: mapped to HTTP 400 (not a field validation error)."""

    pass


@dataclass(frozen=True)
class WebhookResult:
    stripe_event_id: str
    emitted: list[DomainEvent]
    duplicate: bool = False


def verify(payload: bytes, signature: str | None, gateway: PaymentGateway) -> dict[str, Any]:
    if not signature:
        raise InvalidSignature("Missing Stripe-Signature header")
    try:
        return gateway.verify_webhook(payload, signature)
    except (stripe.SignatureVerificationError, ValueError) as error:
        raise InvalidSignature("Invalid Stripe signature") from error


def _forget(stripe_event_id: str) -> None:
    store.client().delete_item(
        TableName=store.table_name(),
        Key={"pk": {"S": f"STRIPE_EVENT#{stripe_event_id}"}, "sk": {"S": "EVENT"}},
    )


def _first_delivery(stripe_event_id: str, event_type: str) -> bool:
    try:
        store.client().put_item(
            TableName=store.table_name(),
            Item={
                "pk": {"S": f"STRIPE_EVENT#{stripe_event_id}"},
                "sk": {"S": "EVENT"},
                "type": {"S": event_type},
            },
            ConditionExpression="attribute_not_exists(pk)",
        )
    except ClientError as error:
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise
    return True


def _payment_data(session: dict[str, Any], stripe_event_id: str) -> dict[str, Any]:
    metadata = session.get("metadata") or {}
    return {
        "booking_id": metadata.get("booking_id") or session.get("client_reference_id"),
        "event_id": metadata.get("event_id"),
        "checkout_session_id": session.get("id"),
        "payment_intent_id": session.get("payment_intent"),
        "amount_cents": session.get("amount_total"),
        "currency": (session.get("currency") or "").upper(),
        "stripe_event_id": stripe_event_id,
    }


def to_domain_events(stripe_event: dict[str, Any]) -> list[DomainEvent]:
    event_type = stripe_event["type"]
    session = stripe_event["data"]["object"]
    data = _payment_data(session, stripe_event["id"])
    if not data["booking_id"]:
        logger.warning(
            "stripe event without booking id", extra={"stripe_event": stripe_event["id"]}
        )
        return []
    if event_type in SUCCEEDED:
        if session.get("payment_status") not in {"paid", "no_payment_required"}:
            return []  # completed but async payment still pending
        return [new_event(PAYMENT_SUCCEEDED, data, service=SERVICE)]
    if event_type in FAILED:
        reason = "expired" if event_type == "checkout.session.expired" else "payment_failed"
        return [new_event(PAYMENT_FAILED, {**data, "reason": reason}, service=SERVICE)]
    return []


def process(
    payload: bytes,
    signature: str | None,
    gateway: PaymentGateway | None = None,
    publisher: EventPublisher | None = None,
) -> WebhookResult:
    """Verify, deduplicate and publish synchronously.

    Publishing happens before we answer Stripe: if the bus rejects the events,
    the dedup marker is removed and the error propagates (HTTP 500), so Stripe
    retries instead of the payment being lost.
    """
    stripe_event = verify(payload, signature, gateway or StripeGateway())
    event_id, event_type = stripe_event["id"], stripe_event["type"]
    if not _first_delivery(event_id, event_type):
        logger.info("duplicate stripe event ignored", extra={"stripe_event": event_id})
        return WebhookResult(event_id, [], duplicate=True)
    emitted = to_domain_events(stripe_event)
    try:
        if emitted:
            (publisher or EventPublisher()).publish(emitted)
    except Exception:
        _forget(event_id)
        raise
    for domain_event in emitted:
        status = "paid" if domain_event.type == PAYMENT_SUCCEEDED else "failed"
        store.mark(domain_event.data["booking_id"], status)
        logger.info(
            "stripe event processed",
            extra={"stripe_event": event_id, "emitted": domain_event.type},
        )
    return WebhookResult(event_id, emitted)
