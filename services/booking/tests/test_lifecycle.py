"""PaymentSucceeded / PaymentFailed / EventCancelled through the Booking consumer."""

from datetime import timedelta

import pytest

from booking import consumers, lifecycle, places, repository
from booking.domain import BookingStatus
from booking.expiry import sweep
from booking.service import request_booking
from localbini_shared.auth import Principal
from localbini_shared.events import EventPublisher, new_event
from localbini_shared.testing import RecordingEventBridge, eventbridge_event

ADA = Principal(user_id="ada", email="ada@example.com")
BOB = Principal(user_id="bob", email="bob@example.com")


@pytest.fixture
def bus(monkeypatch):
    recorder = RecordingEventBridge()
    monkeypatch.setattr(consumers, "EventPublisher", lambda: EventPublisher("bus", client=recorder))
    return recorder


@pytest.fixture
def seed(published_event):
    def _seed(**kwargs):
        event_id = published_event(**kwargs)
        # enrich the projection like a real EventPublished snapshot would
        places.apply_snapshot(
            {
                "event_id": event_id,
                "title": "Sunset jazz",
                "places": kwargs.get("places_total", 10),
                "price_cents": kwargs.get("price_cents", 2500),
                "currency": "CHF",
                "starts_at": places.get(event_id).starts_at.isoformat(),
                "status": "published",
                "important_information": "Bring a blanket.",
                "location": {"name": "Seebad Enge", "address": "Mythenquai 9", "city": "Zürich"},
            },
            "2026-06-01T00:00:00+00:00",
        )
        return event_id

    return _seed


def deliver(type_: str, data: dict, service: str = "payments") -> None:
    event = new_event(type_, data, service=service)
    consumers.handle(eventbridge_event(event.to_detail(), type_), None)


def paid(booking_id: str) -> None:
    deliver("PaymentSucceeded", {"booking_id": booking_id, "amount_cents": 5000})


# --- PaymentSucceeded -------------------------------------------------------------
def test_payment_confirms_booking_and_emits_booking_confirmed(seed, bus) -> None:
    event_id = seed(places_total=10)
    booking, _ = request_booking(ADA, event_id, 2)
    paid(booking.booking_id)

    assert repository.get(booking.booking_id).status is BookingStatus.CONFIRMED
    assert places.get(event_id).places_left == 8  # Hold converted, places stay taken
    [data] = bus.of_type("BookingConfirmed")
    assert data["booking_id"] == booking.booking_id
    assert data["attendee_email"] == "ada@example.com"
    assert data["event"]["important_information"] == "Bring a blanket."
    assert data["event"]["location"]["city"] == "Zürich"


def test_redelivered_payment_confirms_once(seed, bus) -> None:
    booking, _ = request_booking(ADA, seed(), 1)
    paid(booking.booking_id)
    paid(booking.booking_id)
    assert len(bus.of_type("BookingConfirmed")) == 1


def test_payment_after_hold_expiry_is_flagged_for_manual_handling(seed, bus) -> None:
    event_id = seed(places_total=5)
    booking, _ = request_booking(ADA, event_id, 2)
    sweep(
        now=booking.hold_expires_at + timedelta(seconds=1),
        publisher=EventPublisher("b", client=RecordingEventBridge()),
    )

    paid(booking.booking_id)

    flagged = repository.get(booking.booking_id)
    assert flagged.status is BookingStatus.NEEDS_ATTENTION
    assert bus.of_type("BookingConfirmed") == []
    assert places.get(event_id).places_left == 5  # nothing taken twice


def test_payment_for_cancelled_event_is_flagged(seed, bus) -> None:
    event_id = seed()
    booking, _ = request_booking(ADA, event_id, 1)
    deliver(
        "EventCancelled",
        {**_snapshot(event_id), "status": "cancelled"},
        service="catalog",
    )
    paid(booking.booking_id)
    assert repository.get(booking.booking_id).status is BookingStatus.NEEDS_ATTENTION
    assert bus.of_type("BookingConfirmed") == []


# --- PaymentFailed ----------------------------------------------------------------
def test_failed_payment_releases_the_hold_immediately(seed, bus) -> None:
    event_id = seed(places_total=5)
    booking, _ = request_booking(ADA, event_id, 3)
    deliver("PaymentFailed", {"booking_id": booking.booking_id, "reason": "payment_failed"})

    assert places.get(event_id).places_left == 5
    assert repository.get(booking.booking_id).status is BookingStatus.EXPIRED
    [data] = bus.of_type("BookingCancelled")
    assert data["reason"] == "payment_failed"


# --- EventCancelled ---------------------------------------------------------------
def _snapshot(event_id: str) -> dict:
    current = places.get(event_id)
    return {
        "event_id": event_id,
        "title": "Sunset jazz",
        "places": current.places_total,
        "price_cents": current.price_cents,
        "currency": "CHF",
        "starts_at": current.starts_at.isoformat(),
        "location": {"name": "Seebad Enge", "city": "Zürich"},
    }


def test_event_cancelled_cancels_all_bookings_and_lists_attendees(
    seed, bus, bookings_table
) -> None:
    event_id = seed(places_total=10)
    confirmed, _ = request_booking(ADA, event_id, 2)
    paid(confirmed.booking_id)
    pending, _ = request_booking(BOB, event_id, 1)
    expired, _ = request_booking(BOB, event_id, 1)
    lifecycle.expire_hold(event_id, expired.booking_id, 1, "2026-01-01T00:00:00+00:00")

    deliver("EventCancelled", {**_snapshot(event_id), "status": "cancelled"}, service="catalog")

    assert repository.get(confirmed.booking_id).status is BookingStatus.CANCELLED
    assert repository.get(pending.booking_id).status is BookingStatus.CANCELLED
    assert repository.get(expired.booking_id).status is BookingStatus.EXPIRED  # untouched
    assert not places.get(event_id).is_open
    [message] = bus.of_type("EventBookingsCancelled")
    assert message["event"]["title"] == "Sunset jazz"
    by_booking = {a["booking_id"]: a for a in message["attendees"]}
    assert set(by_booking) == {confirmed.booking_id, pending.booking_id}
    assert by_booking[confirmed.booking_id]["was_confirmed"] is True
    assert by_booking[confirmed.booking_id]["attendee_email"] == "ada@example.com"
    holds = [
        i
        for i in places.client().scan(TableName=bookings_table)["Items"]
        if i["sk"]["S"].startswith("HOLD#")
    ]
    assert holds == []  # nothing left for the expiry sweep


def test_redelivered_event_cancelled_does_not_notify_twice(seed, bus) -> None:
    event_id = seed()
    request_booking(ADA, event_id, 1)
    cancelled = {**_snapshot(event_id), "status": "cancelled"}
    deliver("EventCancelled", cancelled, service="catalog")
    deliver("EventCancelled", cancelled, service="catalog")
    assert len(bus.of_type("EventBookingsCancelled")) == 1


def test_attendees_are_chunked(seed, bus, monkeypatch) -> None:
    monkeypatch.setattr(lifecycle, "ATTENDEES_PER_MESSAGE", 2)
    event_id = seed(places_total=10)
    for i in range(5):
        request_booking(Principal(user_id=f"u{i}", email=f"u{i}@example.com"), event_id, 1)
    deliver("EventCancelled", {**_snapshot(event_id), "status": "cancelled"}, service="catalog")

    messages = bus.of_type("EventBookingsCancelled")
    assert [len(m["attendees"]) for m in messages] == [2, 2, 1]
    assert [(m["part"], m["parts"]) for m in messages] == [(1, 3), (2, 3), (3, 3)]


def test_no_bookings_means_no_message(seed, bus) -> None:
    event_id = seed()
    deliver("EventCancelled", {**_snapshot(event_id), "status": "cancelled"}, service="catalog")
    assert bus.of_type("EventBookingsCancelled") == []
