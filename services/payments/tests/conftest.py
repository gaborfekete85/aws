from __future__ import annotations

import os
import uuid

import pytest

os.environ.setdefault("AWS_DEFAULT_REGION", "eu-central-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("EVENT_BUS_NAME", "localbini-test")
os.environ.setdefault("PAYMENTS_TABLE", "localbini-test-payments")


@pytest.fixture
def payments_table(monkeypatch):
    from moto import mock_aws

    from payments import store

    name = f"payments-{uuid.uuid4().hex[:8]}"
    monkeypatch.setenv("PAYMENTS_TABLE", name)
    monkeypatch.delenv("DYNAMODB_ENDPOINT_URL", raising=False)
    store.client.cache_clear()
    with mock_aws():
        store.client().create_table(**store.table_definition(name))
        yield name
    store.client.cache_clear()


class FakeGateway:
    def __init__(self) -> None:
        self.created = []
        self.expired = []

    def create_checkout(self, request):
        from payments.gateway import CheckoutSession

        self.created.append(request)
        return CheckoutSession(
            id=f"cs_test_{request.booking_id}",
            url=f"https://checkout.stripe.com/c/pay/cs_test_{request.booking_id}",
            expires_at=request.expires_at,
        )

    def expire_checkout(self, session_id):
        self.expired.append(session_id)

    def verify_webhook(self, payload, signature):  # pragma: no cover - #26
        raise NotImplementedError


@pytest.fixture
def gateway():
    return FakeGateway()


@pytest.fixture
def booking_requested():
    def factory(**overrides):
        data = {
            "booking_id": str(uuid.uuid4()),
            "event_id": "evt-1",
            "attendee_id": "user-1",
            "attendee_email": "ada@example.com",
            "places": 2,
            "amount_cents": 5000,
            "currency": "CHF",
            "event_title": "Sunset jazz",
            "hold_expires_at": "2026-11-03T12:15:00+00:00",
        }
        data.update(overrides)
        return data

    return factory
