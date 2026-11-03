"""Creating Stripe Checkout sessions for paid Bookings (Stripe mocked)."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from meeton_shared.auth import Principal
from meeton_shared.errors import ForbiddenError
from payments import store
from payments.checkout import (
    checkout_for,
    on_booking_requested,
    on_hold_expired,
    session_expiry,
)
from payments.gateway import STRIPE_MIN_EXPIRY_SECONDS, CheckoutRequest, StripeGateway

ADA = Principal(user_id="user-1")
BOB = Principal(user_id="user-2")


def test_paid_booking_gets_a_checkout_session(payments_table, gateway, booking_requested) -> None:
    data = booking_requested()
    on_booking_requested(data, gateway)

    [request] = gateway.created
    assert request.booking_id == data["booking_id"]
    assert request.places == 2
    assert request.unit_amount_cents == 2500
    assert request.currency == "CHF"
    assert request.customer_email == "ada@example.com"
    assert request.success_url.endswith(f"/checkout/success?booking_id={data['booking_id']}")
    record = store.get(data["booking_id"])
    assert record.status == "open"
    assert record.url.startswith("https://checkout.stripe.com/")


def test_free_booking_never_reaches_stripe(payments_table, gateway, booking_requested) -> None:
    on_booking_requested(booking_requested(amount_cents=0), gateway)
    assert gateway.created == []


def test_redelivered_booking_requested_creates_one_session(
    payments_table, gateway, booking_requested
) -> None:
    data = booking_requested()
    for _ in range(3):
        on_booking_requested(data, gateway)
    assert len(gateway.created) == 1


def test_crash_after_claim_is_retried(payments_table, gateway, booking_requested) -> None:
    data = booking_requested()
    store.claim(data["booking_id"], data["attendee_id"], data["event_id"])  # crashed attempt
    on_booking_requested(data, gateway)
    assert len(gateway.created) == 1
    assert store.get(data["booking_id"]).status == "open"


def test_session_expiry_is_never_before_the_hold_and_respects_stripe_minimum() -> None:
    now = datetime(2026, 11, 3, 12, 0, tzinfo=UTC).timestamp()
    hold_15 = (datetime.fromtimestamp(now, UTC) + timedelta(minutes=15)).isoformat()
    hold_60 = (datetime.fromtimestamp(now, UTC) + timedelta(minutes=60)).isoformat()
    # 15-minute Hold: Stripe's 30-minute floor wins; the session is expired on HoldExpired
    assert session_expiry(hold_15, now) - now >= STRIPE_MIN_EXPIRY_SECONDS
    # longer Hold: the session ends with the Hold
    assert session_expiry(hold_60, now) == int(now) + 3600


def test_hold_expired_expires_the_open_session(payments_table, gateway, booking_requested) -> None:
    data = booking_requested()
    on_booking_requested(data, gateway)
    on_hold_expired({"booking_id": data["booking_id"]}, gateway)
    assert gateway.expired == [f"cs_test_{data['booking_id']}"]
    assert store.get(data["booking_id"]).status == "expired"
    on_hold_expired({"booking_id": data["booking_id"]}, gateway)  # idempotent
    assert len(gateway.expired) == 1


def test_web_app_fetches_url_only_for_own_booking(
    payments_table, gateway, booking_requested
) -> None:
    data = booking_requested()
    assert checkout_for(ADA, data["booking_id"]) is None  # not created yet -> poll
    on_booking_requested(data, gateway)
    assert checkout_for(ADA, data["booking_id"]).url.startswith("https://checkout.stripe.com/")
    with pytest.raises(ForbiddenError):
        checkout_for(BOB, data["booking_id"])


def test_checkout_endpoint_returns_202_then_url(payments_table, gateway, booking_requested) -> None:
    from meeton_shared.testing import http_api_event
    from payments.api import handle

    data = booking_requested()
    event = http_api_event(
        "GET",
        "/bookings/{booking_id}/checkout",
        path_params={"booking_id": data["booking_id"]},
        claims={"sub": "user-1"},
    )
    assert handle(event, None)["statusCode"] == 202
    on_booking_requested(data, gateway)
    result = handle(event, None)
    assert result["statusCode"] == 200
    assert json.loads(result["body"])["url"].startswith("https://checkout.stripe.com/")


def test_stripe_gateway_sends_metadata_and_idempotency_key(monkeypatch) -> None:
    fake_client = MagicMock()
    fake_client.v1.checkout.sessions.create.return_value = MagicMock(
        id="cs_test_1", url="https://checkout.stripe.com/x", expires_at=1_800_000_000
    )
    monkeypatch.setattr(StripeGateway, "client", property(lambda self: fake_client))
    request = CheckoutRequest(
        booking_id="b1",
        event_id="e1",
        event_title="Jazz",
        places=3,
        unit_amount_cents=2500,
        currency="CHF",
        customer_email=None,
        expires_at=1_800_000_000,
        success_url="https://web/success",
        cancel_url="https://web/cancel",
    )
    session = StripeGateway("sk_test_x").create_checkout(request)

    kwargs = fake_client.v1.checkout.sessions.create.call_args.kwargs
    params = kwargs["params"]
    assert kwargs["options"] == {"idempotency_key": "checkout-b1"}
    assert params["mode"] == "payment"
    assert params["metadata"] == {"booking_id": "b1", "event_id": "e1"}
    assert params["client_reference_id"] == "b1"
    assert params["line_items"][0]["quantity"] == 3
    assert params["line_items"][0]["price_data"]["currency"] == "chf"
    assert params["line_items"][0]["price_data"]["unit_amount"] == 2500
    assert params["expires_at"] == 1_800_000_000
    assert "customer_email" not in params  # never send an empty email to Stripe
    assert session.id == "cs_test_1"
