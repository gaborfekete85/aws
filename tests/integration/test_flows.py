"""Cross-service flows on the deployed environment, asserting the domain events on the bus."""

import pytest

from .conftest import eventually

pytestmark = pytest.mark.dev


def test_publish_emits_event_published_and_feeds_booking(http, bus, make_event) -> None:
    event = make_event(places=7, price_cents=1500)

    published = bus.wait_for("EventPublished", lambda d: d["event_id"] == event["id"])
    assert published["source"] == "localbini.catalog"
    assert published["data"]["places"] == 7
    assert published["data"]["price_cents"] == 1500

    def availability_is_projected():
        response = http.get(f"/events/{event['id']}/availability")
        assert response.status_code == 200, response.text
        assert response.json()["places_left"] == 7

    eventually(availability_is_projected)


def test_published_event_is_publicly_searchable(http, make_event) -> None:
    event = make_event()

    def found():
        response = http.get("/events", params={"lat": 47.37, "lng": 8.54, "radius_km": 1})
        assert response.status_code == 200
        assert event["id"] in {e["id"] for e in response.json()["items"]}

    eventually(found, timeout=10)
    assert http.get(f"/events/{event['id']}").json()["status"] == "published"


def test_draft_is_not_public(http, make_event) -> None:
    draft = make_event(publish=False)
    assert http.get(f"/events/{draft['id']}").status_code == 404


def test_free_booking_is_confirmed_and_listed(http, bus, make_event, attendee_headers) -> None:
    event = make_event(price_cents=0, places=3)
    eventually(lambda: _assert_open(http, event["id"]))

    response = http.post(
        f"/events/{event['id']}/bookings", json={"places": 2}, headers=attendee_headers
    )
    assert response.status_code == 201, response.text
    booking = response.json()
    assert booking["status"] == "confirmed"

    confirmed = bus.wait_for("BookingConfirmed", lambda d: d["booking_id"] == booking["booking_id"])
    assert confirmed["data"]["event"]["important_information"] == "Integration test data."
    mine = http.get("/me/bookings", headers=attendee_headers).json()["items"]
    assert booking["booking_id"] in {b["booking_id"] for b in mine}
    assert http.get(f"/events/{event['id']}/availability").json()["places_left"] == 1


def test_no_overbooking_on_the_deployed_stack(http, make_event, attendee_headers) -> None:
    event = make_event(price_cents=0, places=2)
    eventually(lambda: _assert_open(http, event["id"]))
    statuses = [
        http.post(
            f"/events/{event['id']}/bookings", json={"places": 1}, headers=attendee_headers
        ).status_code
        for _ in range(3)
    ]
    assert statuses == [201, 201, 409]


def test_paid_booking_places_a_hold_and_requests_payment(
    http, bus, make_event, attendee_headers
) -> None:
    event = make_event(price_cents=1200, places=4)
    eventually(lambda: _assert_open(http, event["id"]))

    response = http.post(
        f"/events/{event['id']}/bookings", json={"places": 1}, headers=attendee_headers
    )
    assert response.status_code == 201, response.text
    booking = response.json()
    assert booking["status"] == "pending"
    requested = bus.wait_for("BookingRequested", lambda d: d["booking_id"] == booking["booking_id"])
    assert requested["data"]["amount_cents"] == 1200


def test_cancelling_an_event_cancels_its_bookings(
    http, bus, make_event, organizer_headers, attendee_headers
) -> None:
    event = make_event(price_cents=0, places=5)
    eventually(lambda: _assert_open(http, event["id"]))
    booking = http.post(
        f"/events/{event['id']}/bookings", json={"places": 1}, headers=attendee_headers
    ).json()

    assert http.post(f"/events/{event['id']}/cancel", headers=organizer_headers).status_code == 200
    bus.wait_for("EventCancelled", lambda d: d["event_id"] == event["id"])
    notified = bus.wait_for(
        "EventBookingsCancelled", lambda d: d["event"]["event_id"] == event["id"]
    )
    assert booking["booking_id"] in {a["booking_id"] for a in notified["data"]["attendees"]}

    def cancelled():
        status = http.get(f"/bookings/{booking['booking_id']}", headers=attendee_headers).json()[
            "status"
        ]
        assert status == "cancelled"

    eventually(cancelled)


def test_other_attendees_cannot_read_a_booking(
    http, make_event, attendee_headers, organizer_headers
) -> None:
    event = make_event(price_cents=0)
    eventually(lambda: _assert_open(http, event["id"]))
    booking = http.post(
        f"/events/{event['id']}/bookings", json={"places": 1}, headers=attendee_headers
    ).json()
    response = http.get(f"/bookings/{booking['booking_id']}", headers=organizer_headers)
    assert response.status_code == 403


def _assert_open(http, event_id: str) -> None:
    response = http.get(f"/events/{event_id}/availability")
    assert response.status_code == 200 and response.json()["open"], response.text
