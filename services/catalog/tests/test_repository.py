"""Repository integration tests against PostgreSQL + PostGIS."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from catalog.domain import EventStatus, GeoPoint, Location
from catalog.repository import EventRepository
from localbini_shared.errors import NotFoundError

pytestmark = pytest.mark.integration


def test_round_trip_preserves_every_field(session, make_event) -> None:
    repo = EventRepository(session)
    event = make_event(cover_picture_key="covers/abc.jpg")
    repo.add(event)
    session.expire_all()

    loaded = repo.get(event.id)
    assert loaded.title == event.title
    assert loaded.important_information == "Bring a blanket."
    assert loaded.price == event.price
    assert loaded.location.point == GeoPoint(47.3601, 8.5354)
    assert loaded.starts_at == event.starts_at
    assert loaded.status is EventStatus.DRAFT
    assert loaded.cover_picture_key == "covers/abc.jpg"


def test_save_persists_status_and_edits(session, make_event) -> None:
    repo = EventRepository(session)
    event = make_event()
    repo.add(event)
    event.publish()
    event.edit(title="Renamed")
    repo.save(event)
    session.expire_all()

    loaded = repo.get(event.id)
    assert loaded.status is EventStatus.PUBLISHED
    assert loaded.published_at is not None
    assert loaded.title == "Renamed"


def test_location_can_be_replaced(session, make_event) -> None:
    repo = EventRepository(session)
    event = make_event()
    repo.add(event)
    new_location = Location(
        name="Kaufleuten", address="Pelikanstrasse 18", city="Zürich", point=GeoPoint(47.37, 8.535)
    )
    event.edit(location=new_location)
    repo.save(event)
    session.expire_all()
    assert repo.get(event.id).location.name == "Kaufleuten"


def test_get_missing_raises_not_found(session) -> None:
    with pytest.raises(NotFoundError):
        EventRepository(session).get(uuid.uuid4())


def test_list_by_organizer_filters_and_orders(session, make_event) -> None:
    from datetime import timedelta

    repo = EventRepository(session)
    later = make_event(organizer_id="org-x")
    sooner = make_event(organizer_id="org-x", starts_at=later.starts_at - timedelta(days=2))
    other = make_event(organizer_id="org-y")
    for e in (later, sooner, other):
        repo.add(e)
    sooner.publish()
    repo.save(sooner)

    assert [e.id for e in repo.list_by_organizer("org-x")] == [sooner.id, later.id]
    assert [e.id for e in repo.list_by_organizer("org-x", EventStatus.PUBLISHED)] == [sooner.id]


def test_database_constraints_back_up_the_domain(session, make_event) -> None:
    repo = EventRepository(session)
    event = make_event()
    repo.add(event)
    with pytest.raises(IntegrityError), session.begin_nested():
        session.execute(text("update events set places = 0 where id = :id"), {"id": event.id})
