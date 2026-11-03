"""Conditional-write Holds: never more Places taken than exist."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from booking import places
from booking.domain import Booking
from booking.holds import EventNotOpen, HoldRequest, NotEnoughPlaces, place_hold, release_places


def hold(event_id: str, n: int, attendee: str = "u1") -> str:
    booking = Booking.request(
        event_id=event_id,
        attendee_id=attendee,
        attendee_email=None,
        places=n,
        unit_price_cents=100,
        currency="CHF",
        hold_minutes=15,
    )
    req = HoldRequest(booking.booking_id, event_id, attendee, n, booking.hold_expires_at)
    place_hold(req, booking.to_item())
    return booking.booking_id


def test_hold_takes_places(published_event) -> None:
    event_id = published_event(places_total=5)
    hold(event_id, 3)
    assert places.get(event_id).places_left == 2


def test_hold_fails_when_not_enough_places_remain(published_event) -> None:
    event_id = published_event(places_total=2)
    hold(event_id, 2)
    with pytest.raises(NotEnoughPlaces) as info:
        hold(event_id, 1)
    assert info.value.details == {"places_left": 0, "requested": 1}
    assert places.get(event_id).places_left == 0


def test_failed_hold_writes_nothing(published_event, bookings_table) -> None:
    event_id = published_event(places_total=1)
    with pytest.raises(NotEnoughPlaces):
        hold(event_id, 2)
    items = places.client().scan(TableName=bookings_table)["Items"]
    assert [i["sk"]["S"] for i in items] == ["PLACES"]


def test_cannot_hold_on_cancelled_or_unknown_event(published_event) -> None:
    cancelled = published_event(status="cancelled")
    with pytest.raises(EventNotOpen):
        hold(cancelled, 1)
    with pytest.raises(EventNotOpen):
        hold(str(uuid.uuid4()), 1)


def test_release_returns_places_exactly_once(published_event) -> None:
    event_id = published_event(places_total=4)
    booking_id = hold(event_id, 3)
    assert release_places(event_id, booking_id, 3) is True
    assert release_places(event_id, booking_id, 3) is False  # already released
    assert places.get(event_id).places_left == 4


@pytest.mark.integration
def test_concurrent_holds_never_overbook(published_event) -> None:
    """60 Attendees race for 10 places on DynamoDB Local: exactly 10 win."""
    import os

    if not os.environ.get("DYNAMODB_ENDPOINT_URL"):
        pytest.skip("needs DynamoDB Local (docker compose up -d dynamodb)")
    event_id = published_event(places_total=10)

    def attempt(i: int) -> bool:
        try:
            hold(event_id, 1, attendee=f"u{i}")
            return True
        except NotEnoughPlaces:
            return False

    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(attempt, range(60)))

    assert sum(results) == 10
    assert places.get(event_id).places_left == 0


@pytest.mark.integration
def test_concurrent_multi_place_holds_never_overbook(published_event) -> None:
    import os

    if not os.environ.get("DYNAMODB_ENDPOINT_URL"):
        pytest.skip("needs DynamoDB Local")
    event_id = published_event(places_total=10)

    def attempt(i: int) -> int:
        n = 1 + i % 3  # 1, 2 or 3 places
        try:
            hold(event_id, n, attendee=f"u{i}")
            return n
        except NotEnoughPlaces:
            return 0

    with ThreadPoolExecutor(max_workers=16) as pool:
        taken = sum(pool.map(attempt, range(40)))

    left = places.get(event_id).places_left
    assert taken + left == 10
    assert left >= 0


def test_booking_amount_and_bounds() -> None:
    from localbini_shared.errors import ValidationError

    booking = Booking.request(
        event_id="e",
        attendee_id="u",
        attendee_email=None,
        places=3,
        unit_price_cents=2500,
        currency="CHF",
        hold_minutes=15,
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert booking.amount_cents == 7500
    assert booking.hold_expires_at == datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=15)
    for bad in (0, 11):
        with pytest.raises(ValidationError):
            Booking.request(
                event_id="e",
                attendee_id="u",
                attendee_email=None,
                places=bad,
                unit_price_cents=1,
                currency="CHF",
                hold_minutes=15,
            )
