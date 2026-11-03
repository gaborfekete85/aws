from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest

os.environ.setdefault("AWS_DEFAULT_REGION", "eu-central-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("EVENT_BUS_NAME", "localbini-test")
os.environ.setdefault("BOOKINGS_TABLE", "localbini-test-bookings")

FUTURE = (datetime.now(UTC) + timedelta(days=30)).replace(microsecond=0)


def _create_table(name: str) -> None:
    from booking import table

    table.client().create_table(**table.table_definition(name))
    table.client().get_waiter("table_exists").wait(TableName=name)


@pytest.fixture
def bookings_table(monkeypatch):
    """A fresh Bookings table: DynamoDB Local when DYNAMODB_ENDPOINT_URL is set, else moto."""
    from booking import table

    name = f"bookings-{uuid.uuid4().hex[:8]}"
    monkeypatch.setenv("BOOKINGS_TABLE", name)
    table.client.cache_clear()
    if os.environ.get("DYNAMODB_ENDPOINT_URL"):
        _create_table(name)
        try:
            yield name
        finally:
            table.client().delete_table(TableName=name)
            table.client.cache_clear()
    else:
        from moto import mock_aws

        with mock_aws():
            import boto3

            boto3.client("events").create_event_bus(Name=os.environ["EVENT_BUS_NAME"])
            _create_table(name)
            try:
                yield name
            finally:
                table.client.cache_clear()


@pytest.fixture
def published_event(bookings_table):
    """Seed an EventPlaces projection as if EventPublished had been consumed."""
    from booking import places

    def _seed(*, places_total: int = 10, price_cents: int = 2500, starts_at=FUTURE, **extra):
        event_id = extra.pop("event_id", str(uuid.uuid4()))
        places.apply_snapshot(
            {
                "event_id": event_id,
                "title": extra.pop("title", "Sunset jazz"),
                "places": places_total,
                "price_cents": price_cents,
                "currency": "CHF",
                "starts_at": starts_at.isoformat(),
                "status": extra.pop("status", "published"),
            },
            extra.pop("occurred_at", "2026-01-01T00:00:00+00:00"),
        )
        return event_id

    return _seed


ATTENDEE = {"sub": "user-1", "email": "ada@example.com"}
OTHER_ATTENDEE = {"sub": "user-2", "email": "bob@example.com"}
ADMIN = {"sub": "admin-1", "cognito:groups": "[admin]"}


@pytest.fixture
def bus():
    from localbini_shared.testing import capture_lbz_events, release_lbz_events

    recorder = capture_lbz_events()
    yield recorder
    release_lbz_events()


@pytest.fixture
def call(bookings_table, bus):
    import json

    from booking.api import handle
    from localbini_shared.testing import http_api_event

    def _call(method, route, *, claims=None, body=None, path=None):
        result = handle(
            http_api_event(method, route, path_params=path, body=body, claims=claims), None
        )
        return result["statusCode"], json.loads(result["body"]) if result["body"] else None

    return _call
