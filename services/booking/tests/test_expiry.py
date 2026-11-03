"""Expired Holds release their Places exactly once (scheduled sweep)."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from booking import places, repository
from booking.domain import BookingStatus
from booking.expiry import sweep
from booking.holds import HoldGone, convert_hold
from booking.service import request_booking
from localbini_shared.auth import Principal
from localbini_shared.testing import RecordingEventBridge

ADA = Principal(user_id="ada", email="ada@example.com")


class Publisher:
    def __init__(self) -> None:
        self.recorder = RecordingEventBridge()

    def publish(self, events):
        from localbini_shared.events import EventPublisher

        return EventPublisher("bus", client=self.recorder).publish(events)


@pytest.fixture
def publisher():
    return Publisher()


def hold(event_id, n=2, now=None):
    booking, _ = request_booking(ADA, event_id, n, now=now)
    return booking


def test_hold_is_not_released_before_its_window(published_event, publisher) -> None:
    event_id = published_event(places_total=5)
    booking = hold(event_id)
    result = sweep(now=booking.hold_expires_at - timedelta(seconds=1), publisher=publisher)
    assert result == {"released": 0, "skipped": 0}
    assert places.get(event_id).places_left == 3


def test_expired_hold_returns_places_and_emits_hold_expired(published_event, publisher) -> None:
    event_id = published_event(places_total=5)
    booking = hold(event_id)
    result = sweep(now=booking.hold_expires_at + timedelta(seconds=1), publisher=publisher)

    assert result == {"released": 1, "skipped": 0}
    assert places.get(event_id).places_left == 5
    assert repository.get(booking.booking_id).status is BookingStatus.EXPIRED
    [data] = publisher.recorder.of_type("HoldExpired")
    assert data["booking_id"] == booking.booking_id
    assert data["places"] == 2


def test_default_window_is_15_minutes(published_event) -> None:
    start = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
    booking = hold(published_event(), now=start)
    assert booking.hold_expires_at == start + timedelta(minutes=15)


def test_window_is_configurable(published_event, monkeypatch) -> None:
    monkeypatch.setenv("HOLD_MINUTES", "5")
    start = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
    assert hold(published_event(), now=start).hold_expires_at == start + timedelta(minutes=5)


def test_released_exactly_once_across_repeated_sweeps(published_event, publisher) -> None:
    event_id = published_event(places_total=5)
    booking = hold(event_id, 3)
    later = booking.hold_expires_at + timedelta(minutes=1)
    sweep(now=later, publisher=publisher)
    assert sweep(now=later, publisher=publisher) == {"released": 0, "skipped": 0}
    assert places.get(event_id).places_left == 5
    assert len(publisher.recorder.of_type("HoldExpired")) == 1


@pytest.mark.integration
def test_parallel_sweeps_release_exactly_once(published_event) -> None:
    import os

    if not os.environ.get("DYNAMODB_ENDPOINT_URL"):
        pytest.skip("needs DynamoDB Local")
    event_id = published_event(places_total=20)
    bookings = [hold(event_id, 2) for _ in range(5)]
    later = max(b.hold_expires_at for b in bookings) + timedelta(minutes=1)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: sweep(now=later, publisher=Publisher()), range(8)))

    assert sum(r["released"] for r in results) == 5
    assert places.get(event_id).places_left == 20


def test_payment_in_time_converts_hold_and_sweep_skips_it(published_event, publisher) -> None:
    event_id = published_event(places_total=5)
    booking = hold(event_id, 2)
    convert_hold(event_id, booking.booking_id, datetime.now(UTC).isoformat())

    assert repository.get(booking.booking_id).status is BookingStatus.CONFIRMED
    sweep(now=booking.hold_expires_at + timedelta(minutes=1), publisher=publisher)
    assert places.get(event_id).places_left == 3  # confirmed places stay taken
    assert publisher.recorder.of_type("HoldExpired") == []


def test_late_payment_after_expiry_finds_no_hold(published_event, publisher) -> None:
    event_id = published_event(places_total=5)
    booking = hold(event_id, 2)
    sweep(now=booking.hold_expires_at + timedelta(seconds=1), publisher=publisher)

    with pytest.raises(HoldGone):
        convert_hold(event_id, booking.booking_id, datetime.now(UTC).isoformat())
    assert repository.get(booking.booking_id).status is BookingStatus.EXPIRED
    assert places.get(event_id).places_left == 5  # nothing taken twice


def test_free_bookings_have_no_hold_to_expire(published_event, publisher) -> None:
    event_id = published_event(places_total=5, price_cents=0)
    booking = hold(event_id, 2)
    sweep(now=datetime.now(UTC) + timedelta(days=1), publisher=publisher)
    assert repository.get(booking.booking_id).status is BookingStatus.CONFIRMED
    assert places.get(event_id).places_left == 3


def test_ttl_is_only_garbage_collection(published_event, bookings_table) -> None:
    event_id = published_event()
    booking = hold(event_id)
    item = places.client().get_item(
        TableName=bookings_table,
        Key={"pk": {"S": f"EVENT#{event_id}"}, "sk": {"S": f"HOLD#{booking.booking_id}"}},
    )["Item"]
    ttl = int(item["expires_at"]["N"])
    assert ttl == int(booking.hold_expires_at.timestamp()) + 24 * 3600
