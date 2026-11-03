"""Public Event search: radius edges, date boundaries, pagination, GiST index use."""

from datetime import UTC, datetime, timedelta

import pytest
from catalog.domain import GeoPoint, Location
from catalog.repository import EventRepository
from catalog.search import SearchQuery, search_published
from localbini_shared.errors import ValidationError
from sqlalchemy import text

pytestmark = pytest.mark.integration

ORIGIN = GeoPoint(47.3769, 8.5417)  # Zürich HB
T0 = datetime(2031, 6, 1, 18, 0, tzinfo=UTC)


def point_at(session, km: float, azimuth_deg: float = 0.0) -> GeoPoint:
    """Exact geodesic point `km` from ORIGIN (PostGIS does the spheroid math)."""
    row = session.execute(
        text(
            "select ST_Y(p::geometry), ST_X(p::geometry) from ("
            " select ST_Project(ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,"
            " :meters, radians(:az)) as p) s"
        ),
        {"lng": ORIGIN.lng, "lat": ORIGIN.lat, "meters": km * 1000, "az": azimuth_deg},
    ).one()
    return GeoPoint(lat=row[0], lng=row[1])


@pytest.fixture
def seed(session, make_event):
    repo = EventRepository(session)

    def _seed(*, km: float = 1.0, starts_at: datetime = T0, publish: bool = True, title="E"):
        location = Location(
            name=f"{km} km", address="Somewhere 1", city="Zürich", point=point_at(session, km)
        )
        event = make_event(title=title, location=location, starts_at=starts_at)
        repo.add(event)
        if publish:
            event.publish(now=starts_at - timedelta(days=30))
            repo.save(event)
        return event

    return _seed


def ids(page) -> list:
    return [h.event.id for h in page.hits]


def near(**kwargs) -> SearchQuery:
    defaults = {
        "lat": ORIGIN.lat,
        "lng": ORIGIN.lng,
        "radius_km": 10,
        "starts_from": T0 - timedelta(days=1),
    }
    return SearchQuery(**{**defaults, **kwargs})


def test_only_published_events_are_found(session, seed) -> None:
    published = seed()
    seed(publish=False)  # draft
    cancelled = seed()
    cancelled.cancel(now=T0 - timedelta(days=1))
    EventRepository(session).save(cancelled)

    assert ids(search_published(session, near())) == [published.id]


def test_radius_edges(session, seed) -> None:
    inside = seed(km=9.95)
    seed(km=10.05)
    page = search_published(session, near(radius_km=10))
    assert ids(page) == [inside.id]
    assert page.hits[0].distance_km == pytest.approx(9.95, abs=0.01)


def test_radius_includes_the_exact_boundary(session, seed) -> None:
    on_edge = seed(km=10.0)
    assert ids(search_published(session, near(radius_km=10.0005))) == [on_edge.id]


def test_date_range_is_inclusive_on_both_ends(session, seed) -> None:
    at_from = seed(starts_at=T0)
    at_to = seed(starts_at=T0 + timedelta(days=2))
    seed(starts_at=T0 - timedelta(seconds=1))
    seed(starts_at=T0 + timedelta(days=2, seconds=1))
    page = search_published(session, near(starts_from=T0, starts_to=T0 + timedelta(days=2)))
    assert ids(page) == [at_from.id, at_to.id]


def test_past_events_are_hidden_by_default(session, seed) -> None:
    seed(starts_at=datetime.now(UTC) - timedelta(hours=1))
    future = seed(starts_at=datetime.now(UTC) + timedelta(days=3))
    page = search_published(session, SearchQuery(lat=ORIGIN.lat, lng=ORIGIN.lng, radius_km=10))
    assert ids(page) == [future.id]


def test_ordered_by_start_and_paginated(session, seed) -> None:
    events = [seed(starts_at=T0 + timedelta(hours=h)) for h in (5, 1, 3, 2, 4)]
    expected = [e.id for e in sorted(events, key=lambda e: e.starts_at)]

    first = search_published(session, near(limit=2, offset=0))
    second = search_published(session, near(limit=2, offset=2))
    last = search_published(session, near(limit=2, offset=4))

    assert first.total == 5
    assert ids(first) + ids(second) + ids(last) == expected
    assert (first.next_offset, second.next_offset, last.next_offset) == (2, 4, None)


def test_without_coordinates_searches_by_date_only(session, seed) -> None:
    far = seed(km=150)
    page = search_published(session, SearchQuery(starts_from=T0 - timedelta(days=1)))
    assert far.id in ids(page)
    assert all(h.distance_km is None for h in page.hits)


def test_search_uses_the_gist_index(session, seed) -> None:
    seed()
    session.execute(text("set local enable_seqscan = off"))
    plan = "\n".join(
        r[0]
        for r in session.execute(
            text(
                "explain select e.id from events e join locations l on l.id = e.location_id"
                " where ST_DWithin(l.point,"
                " ST_SetSRID(ST_MakePoint(8.54, 47.37), 4326)::geography, 10000)"
            )
        )
    )
    assert "ix_locations_point" in plan


@pytest.mark.parametrize(
    "kwargs",
    [
        {"lat": 47.0},  # lng missing
        {"lat": 47.0, "lng": 8.0, "radius_km": 0},
        {"lat": 47.0, "lng": 8.0, "radius_km": 500},
        {"limit": 0},
        {"limit": 51},
        {"offset": -1},
        {"starts_from": T0, "starts_to": T0 - timedelta(days=1)},
    ],
)
def test_invalid_queries_are_rejected(kwargs) -> None:
    with pytest.raises(ValidationError):
        SearchQuery(**kwargs)
