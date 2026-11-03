"""Booking API through the lbz handler."""

from datetime import UTC, datetime, timedelta

import pytest
from booking import places

from .conftest import ADMIN, ATTENDEE, OTHER_ATTENDEE


def book(call, event_id, n=2, claims=ATTENDEE):
    return call(
        "POST",
        "/events/{event_id}/bookings",
        claims=claims,
        path={"event_id": event_id},
        body={"places": n},
    )


def test_paid_event_places_a_hold_and_emits_booking_requested(call, published_event, bus) -> None:
    event_id = published_event(places_total=10, price_cents=2500)
    status, body = book(call, event_id, 2)

    assert status == 201
    assert body["status"] == "pending"
    assert body["amount_cents"] == 5000
    assert body["hold_expires_at"]
    assert places.get(event_id).places_left == 8
    [data] = bus.of_type("BookingRequested")
    assert data["booking_id"] == body["booking_id"]
    assert data["attendee_email"] == "ada@example.com"
    assert data["amount_cents"] == 5000
    assert bus.of_type("BookingConfirmed") == []


def test_free_event_is_confirmed_immediately(call, published_event, bus, bookings_table) -> None:
    event_id = published_event(places_total=10, price_cents=0)
    status, body = book(call, event_id, 3)

    assert (status, body["status"]) == (201, "confirmed")
    assert body["hold_expires_at"] is None
    assert places.get(event_id).places_left == 7
    [data] = bus.of_type("BookingConfirmed")
    assert data["booking_id"] == body["booking_id"]
    assert data["event"]["title"] == "Sunset jazz"
    assert bus.of_type("BookingRequested") == []
    sks = {i["sk"]["S"] for i in places.client().scan(TableName=bookings_table)["Items"]}
    assert not any(sk.startswith("HOLD#") for sk in sks)  # nothing to expire


def test_not_enough_places_is_409_with_places_left(call, published_event, bus) -> None:
    event_id = published_event(places_total=3)
    book(call, event_id, 2)
    status, body = book(call, event_id, 2, claims=OTHER_ATTENDEE)
    assert status == 409
    assert body["places_left"] == 1
    assert len(bus.of_type("BookingRequested")) == 1


def test_rejects_cancelled_event(call, published_event) -> None:
    event_id = published_event(status="cancelled")
    assert book(call, event_id)[0] == 409


def test_rejects_unpublished_event(call, bookings_table) -> None:
    status, _ = book(call, "never-published")
    assert status == 404


def test_rejects_past_event(call, published_event) -> None:
    event_id = published_event(starts_at=datetime.now(UTC) - timedelta(hours=1))
    status, body = book(call, event_id)
    assert status == 409
    assert "started" in body["message"]


@pytest.mark.parametrize("n", [0, 11])
def test_places_bounds_are_422(call, published_event, n) -> None:
    assert book(call, published_event(), n)[0] == 422


def test_visitor_must_log_in(call, published_event) -> None:
    assert book(call, published_event(), claims=None)[0] == 401


def test_my_bookings_lists_only_mine_newest_first(call, published_event) -> None:
    first = published_event(title="First")
    second = published_event(title="Second")
    _, a = book(call, first, 1)
    _, b = book(call, second, 1)
    book(call, first, 1, claims=OTHER_ATTENDEE)

    status, body = call("GET", "/me/bookings", claims=ATTENDEE)
    assert status == 200
    assert [x["booking_id"] for x in body["items"]] == [b["booking_id"], a["booking_id"]]
    assert {x["event_title"] for x in body["items"]} == {"First", "Second"}


def test_booking_detail_is_owner_or_admin_only(call, published_event) -> None:
    _, booking = book(call, published_event())
    path = {"booking_id": booking["booking_id"]}
    assert call("GET", "/bookings/{booking_id}", claims=ATTENDEE, path=path)[0] == 200
    assert call("GET", "/bookings/{booking_id}", claims=ADMIN, path=path)[0] == 200
    assert call("GET", "/bookings/{booking_id}", claims=OTHER_ATTENDEE, path=path)[0] == 403
    assert call("GET", "/bookings/{booking_id}", claims=None, path=path)[0] == 401


def test_availability_is_public(call, published_event) -> None:
    event_id = published_event(places_total=5, price_cents=1000)
    book(call, event_id, 2)
    status, body = call("GET", "/events/{event_id}/availability", path={"event_id": event_id})
    assert status == 200
    assert body == {
        "event_id": event_id,
        "places_total": 5,
        "places_left": 3,
        "price_cents": 1000,
        "currency": "CHF",
        "open": True,
    }
