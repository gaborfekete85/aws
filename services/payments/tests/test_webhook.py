"""Stripe webhook: real signature verification over Stripe-CLI-shaped fixture payloads."""

import hashlib
import hmac
import json
import time
from pathlib import Path

import pytest

from meeton_shared.events import PublishError
from meeton_shared.testing import RecordingEventBridge
from payments import store
from payments.gateway import StripeGateway
from payments.webhook import InvalidSignature, process

FIXTURES = Path(__file__).parent / "fixtures"
SIGNING_SECRET = "test-signing-secret"  # stands in for the endpoint's signing secret


def payload(name: str, booking_id: str = "b-1") -> bytes:
    raw = (FIXTURES / name).read_text().replace("BOOKING_ID", booking_id)
    return raw.replace("EVENT_ID", "evt-1").encode()


def sign(body: bytes, secret: str = SIGNING_SECRET, timestamp: int | None = None) -> str:
    """Stripe's scheme: t=<ts>,v1=HMAC_SHA256(secret, '<ts>.<body>')."""
    ts = timestamp or int(time.time())
    mac = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={ts},v1={mac}"


@pytest.fixture
def gateway():
    return StripeGateway(api_key="unused", webhook_secret=SIGNING_SECRET)


@pytest.fixture
def bus():
    return RecordingEventBridge()


@pytest.fixture
def publisher(bus):
    from meeton_shared.events import EventPublisher

    return EventPublisher("bus", client=bus)


def test_completed_session_emits_payment_succeeded(payments_table, gateway, publisher, bus) -> None:
    store.claim("b-1", "user-1", "evt-1")
    body = payload("checkout.session.completed.json")
    result = process(body, sign(body), gateway, publisher)

    assert not result.duplicate
    [data] = bus.of_type("PaymentSucceeded")
    assert data["booking_id"] == "b-1"
    assert data["event_id"] == "evt-1"
    assert data["amount_cents"] == 5000
    assert data["currency"] == "CHF"
    assert data["payment_intent_id"] == "pi_test_3Q1"
    assert data["stripe_event_id"] == "evt_test_completed"
    assert store.get("b-1").status == "paid"


def test_async_payment_succeeded_also_succeeds(payments_table, gateway, publisher, bus) -> None:
    body = payload("checkout.session.async_payment_succeeded.json")
    process(body, sign(body), gateway, publisher)
    assert len(bus.of_type("PaymentSucceeded")) == 1


def test_completed_but_unpaid_waits_for_async_result(
    payments_table, gateway, publisher, bus
) -> None:
    body = payload("checkout.session.completed.unpaid.json")
    process(body, sign(body), gateway, publisher)
    assert bus.events == []


@pytest.mark.parametrize(
    ("fixture", "reason"),
    [
        ("checkout.session.async_payment_failed.json", "payment_failed"),
        ("checkout.session.expired.json", "expired"),
    ],
)
def test_failures_emit_payment_failed(
    payments_table, gateway, publisher, bus, fixture, reason
) -> None:
    store.claim("b-1", "user-1", "evt-1")
    body = payload(fixture)
    process(body, sign(body), gateway, publisher)
    [data] = bus.of_type("PaymentFailed")
    assert (data["booking_id"], data["reason"]) == ("b-1", reason)
    assert store.get("b-1").status == "failed"


def test_unrelated_event_types_are_acknowledged_silently(
    payments_table, gateway, publisher, bus
) -> None:
    body = payload("payment_intent.created.json")
    assert not process(body, sign(body), gateway, publisher).duplicate
    assert bus.events == []


def test_redelivery_is_idempotent(payments_table, gateway, publisher, bus) -> None:
    body = payload("checkout.session.completed.json")
    first = process(body, sign(body), gateway, publisher)
    again = process(body, sign(body), gateway, publisher)
    assert (first.duplicate, again.duplicate) == (False, True)
    assert len(bus.of_type("PaymentSucceeded")) == 1


@pytest.mark.parametrize(
    "signature",
    [
        None,
        "",
        "t=1,v1=deadbeef",
        sign(b"different body"),
        sign(payload("checkout.session.completed.json"), secret="someone-else"),
        sign(
            payload("checkout.session.completed.json"), timestamp=int(time.time()) - 3600
        ),  # replay
    ],
    ids=["missing", "empty", "garbage", "other-body", "wrong-secret", "too-old"],
)
def test_invalid_signatures_are_rejected(
    payments_table, gateway, publisher, bus, signature
) -> None:
    with pytest.raises(InvalidSignature):
        process(payload("checkout.session.completed.json"), signature, gateway, publisher)
    assert bus.events == []


class BrokenBus:
    def put_events(self, Entries):
        return {"Entries": [{"ErrorCode": "InternalFailure"} for _ in Entries]}


def test_bus_failure_makes_stripe_retry_instead_of_losing_the_payment(
    payments_table, gateway, bus
) -> None:
    from meeton_shared.events import EventPublisher

    body = payload("checkout.session.completed.json")
    with pytest.raises(PublishError):
        process(body, sign(body), gateway, EventPublisher("bus", client=BrokenBus()))
    # Stripe retries: the dedup marker was rolled back, so the retry is processed
    retry = process(body, sign(body), gateway, EventPublisher("bus", client=bus))
    assert not retry.duplicate
    assert len(bus.of_type("PaymentSucceeded")) == 1


def test_webhook_route_returns_400_on_bad_signature(payments_table, monkeypatch) -> None:
    from meeton_shared.testing import http_api_event
    from payments import webhook
    from payments.api import handle

    monkeypatch.setattr(
        webhook, "StripeGateway", lambda: StripeGateway(api_key="x", webhook_secret=SIGNING_SECRET)
    )
    event = http_api_event(
        "POST", "/payments/stripe/webhook", headers={"Stripe-Signature": "t=1,v1=bad"}
    )
    event["body"] = payload("checkout.session.completed.json").decode()
    result = handle(event, None)
    assert result["statusCode"] == 400


def test_webhook_route_verifies_the_raw_body(payments_table, monkeypatch, bus) -> None:
    from meeton_shared.events import EventPublisher
    from meeton_shared.testing import http_api_event
    from payments import webhook
    from payments.api import handle

    monkeypatch.setattr(
        webhook, "StripeGateway", lambda: StripeGateway(api_key="x", webhook_secret=SIGNING_SECRET)
    )
    monkeypatch.setattr(webhook, "EventPublisher", lambda: EventPublisher("bus", client=bus))
    body = payload("checkout.session.completed.json")
    event = http_api_event(
        "POST", "/payments/stripe/webhook", headers={"Stripe-Signature": sign(body)}
    )
    event["body"] = body.decode()  # exactly the bytes Stripe signed
    result = handle(event, None)
    assert result["statusCode"] == 200
    assert json.loads(result["body"]) == {"received": True, "duplicate": False}
    assert len(bus.of_type("PaymentSucceeded")) == 1
