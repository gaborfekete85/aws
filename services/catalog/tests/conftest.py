from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("AWS_DEFAULT_REGION", "eu-central-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("EVENT_BUS_NAME", "localbini-test")


def _pg_available() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


@pytest.fixture(scope="session")
def migrated_engine() -> Iterator[object]:
    """A real Postgres/PostGIS database at head (docker compose up -d postgres)."""
    if not _pg_available():
        pytest.skip("DATABASE_URL not set (docker compose up -d postgres)")
    from catalog.db import get_engine
    from catalog.migrate import upgrade

    upgrade()
    yield get_engine()


@pytest.fixture
def session(migrated_engine):
    """A session inside a transaction that is rolled back after each test."""
    from sqlalchemy.orm import Session

    connection = migrated_engine.connect()
    transaction = connection.begin()
    db_session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield db_session
    finally:
        db_session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def make_event():
    from datetime import UTC, datetime, timedelta

    from catalog.domain import Event, GeoPoint, Location, Money

    def factory(**overrides):
        starts = overrides.pop("starts_at", datetime.now(UTC) + timedelta(days=7))
        values = {
            "organizer_id": "org-1",
            "title": "Sunset jazz on the lake",
            "description": "Live quartet.",
            "important_information": "Bring a blanket.",
            "starts_at": starts,
            "ends_at": starts + timedelta(hours=2),
            "places": 40,
            "price": Money(2500, "CHF"),
            "location": Location(
                name="Seebad Enge",
                address="Mythenquai 9",
                city="Zürich",
                point=GeoPoint(47.3601, 8.5354),
            ),
        }
        values.update(overrides)
        return Event(**values)

    return factory
