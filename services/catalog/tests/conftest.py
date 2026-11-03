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


ORGANIZER = {"sub": "org-1", "email": "org@example.com", "cognito:groups": "[organizer]"}
OTHER_ORGANIZER = {"sub": "org-2", "cognito:groups": "[organizer]"}
ADMIN = {"sub": "admin-1", "cognito:groups": "[admin]"}
ATTENDEE = {"sub": "user-1", "email": "user@example.com"}


class StubGeocoder:
    """Resolves every address to central Zürich, or fails for 'Atlantis'."""

    async def geocode(self, address: str, city: str):
        from catalog.domain import GeoPoint
        from catalog.geocoding import AddressNotFound, GeocodeResult

        if city == "Atlantis":
            raise AddressNotFound(
                f"We could not find '{address}, {city}'", details={"field": "address"}
            )
        return GeocodeResult(GeoPoint(47.3769, 8.5417), f"{address}, {city}")


@pytest.fixture
def catalog_api(migrated_engine):
    """The Catalog Lambda handler wired to the test DB, a stub geocoder and a moto bus."""
    from moto import mock_aws
    from sqlalchemy import text
    from sqlalchemy.orm import sessionmaker

    from catalog.api import CatalogResource, handle

    factory = sessionmaker(bind=migrated_engine, expire_on_commit=False)
    original = (CatalogResource.session_provider, CatalogResource.geocoder_provider)
    CatalogResource.session_provider = staticmethod(factory)
    CatalogResource.geocoder_provider = staticmethod(StubGeocoder)
    with mock_aws():
        import boto3

        boto3.client("events").create_event_bus(Name=os.environ["EVENT_BUS_NAME"])
        try:
            yield handle
        finally:
            CatalogResource.session_provider, CatalogResource.geocoder_provider = original
            with migrated_engine.begin() as conn:
                conn.execute(text("truncate events, locations cascade"))


@pytest.fixture
def call(catalog_api):
    import json

    from localbini_shared.testing import http_api_event

    def _call(method, route, *, claims=None, body=None, path=None, query=None):
        event = http_api_event(
            method, route, path_params=path, body=body, claims=claims, query=query
        )
        result = catalog_api(event, None)
        return result["statusCode"], json.loads(result["body"]) if result["body"] else None

    return _call


@pytest.fixture
def event_body():
    from datetime import UTC, datetime, timedelta

    starts = (datetime.now(UTC) + timedelta(days=14)).replace(microsecond=0)

    def factory(**overrides):
        body = {
            "title": "Sunset jazz on the lake",
            "description": "Live quartet.",
            "important_information": "Bring a blanket.",
            "starts_at": starts.isoformat(),
            "ends_at": (starts + timedelta(hours=2)).isoformat(),
            "places": 40,
            "price_cents": 2500,
            "currency": "CHF",
            "location": {"name": "Seebad Enge", "address": "Mythenquai 9", "city": "Zürich"},
        }
        body.update(overrides)
        return body

    return factory


@pytest.fixture
def sent_events():
    from lbz.events.api import EventAPI

    def _sent():
        return [(e.type, e.data) for e in EventAPI().sent_events]

    return _sent


@pytest.fixture
def media(catalog_api):
    """A moto S3 media bucket wired into the Catalog API (inside catalog_api's mock_aws)."""
    import boto3

    from catalog.api import CatalogResource
    from catalog.media import CoverPictures

    s3 = boto3.client("s3", region_name="eu-central-1")
    s3.create_bucket(
        Bucket="localbini-test-media",
        CreateBucketConfiguration={"LocationConstraint": "eu-central-1"},
    )
    covers = CoverPictures("localbini-test-media", "cdn.example.net", client=s3)
    original = CatalogResource.covers_provider
    CatalogResource.covers_provider = staticmethod(lambda: covers)
    try:
        yield s3
    finally:
        CatalogResource.covers_provider = original
