"""Create (and expire) Stripe Checkout sessions for paid Bookings."""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any

from meeton_shared.auth import Principal, require_authenticated
from meeton_shared.errors import ForbiddenError
from meeton_shared.logging import get_logger
from payments import store
from payments.gateway import (
    STRIPE_MIN_EXPIRY_SECONDS,
    CheckoutRequest,
    PaymentGateway,
    StripeGateway,
)

logger = get_logger(__name__)


def session_expiry(hold_expires_at: str | None, now: float | None = None) -> int:
    """Stripe's minimum (30 min) or the Hold expiry, whichever is later.

    Stripe cannot expire a session sooner than 30 minutes, so when the Hold is
    shorter the session is expired actively on HoldExpired (see on_hold_expired).
    """
    now = now if now is not None else time.time()
    floor = int(now) + STRIPE_MIN_EXPIRY_SECONDS + 60
    if hold_expires_at is None:
        return floor
    hold = int(datetime.fromisoformat(hold_expires_at).timestamp())
    return max(hold, floor)


def web_url() -> str:
    return os.environ.get("WEB_URL", "http://localhost:5173").rstrip("/")


def on_booking_requested(data: dict[str, Any], gateway: PaymentGateway | None = None) -> None:
    if int(data["amount_cents"]) == 0:
        return  # free Events never reach Checkout
    booking_id = data["booking_id"]
    if not store.claim(booking_id, data["attendee_id"], data["event_id"]):
        logger.info("checkout already handled", extra={"booking_id": booking_id})
        existing = store.get(booking_id)
        if existing.status != "creating":
            return
        # a previous attempt crashed mid-way: retry; Stripe's idempotency key dedupes
    gateway = gateway or StripeGateway()
    places = int(data["places"])
    session = gateway.create_checkout(
        CheckoutRequest(
            booking_id=booking_id,
            event_id=data["event_id"],
            event_title=data.get("event_title", ""),
            places=places,
            unit_amount_cents=int(data["amount_cents"]) // places,
            currency=data["currency"],
            customer_email=data.get("attendee_email"),
            expires_at=session_expiry(data.get("hold_expires_at")),
            success_url=f"{web_url()}/checkout/success?booking_id={booking_id}",
            cancel_url=f"{web_url()}/checkout/cancel?booking_id={booking_id}",
        )
    )
    store.update(
        booking_id,
        status="open",
        session_id=session.id,
        url=session.url,
        expires_at=datetime.fromtimestamp(session.expires_at).astimezone().isoformat(),
    )
    logger.info("checkout session created", extra={"booking_id": booking_id})


def on_hold_expired(data: dict[str, Any], gateway: PaymentGateway | None = None) -> None:
    """The Hold is gone: make sure the Attendee can no longer pay."""
    record = store.find(data["booking_id"])
    if record is None or record.session_id is None or record.status != "open":
        return
    (gateway or StripeGateway()).expire_checkout(record.session_id)
    store.update(record.booking_id, status="expired")


def checkout_for(principal: Principal, booking_id: str) -> store.CheckoutRecord | None:
    """The Attendee's Checkout; None while the session is still being created."""
    user_id = require_authenticated(principal)
    record = store.find(booking_id)
    if record is None:
        return None
    if record.attendee_id != user_id and not principal.is_admin:
        raise ForbiddenError("This is not your Booking")
    return record if record.status != "creating" else None
