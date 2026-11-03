"""EventPlaces projection kept in sync from Catalog events."""

from booking import places
from booking.consumers import handle
from meeton_shared.events import new_event
from meeton_shared.testing import eventbridge_event


def snapshot(event_id: str, **overrides):
    data = {
        "event_id": event_id,
        "title": "Jazz",
        "places": 10,
        "price_cents": 2500,
        "currency": "CHF",
        "starts_at": "2031-01-01T18:00:00+00:00",
        "status": "published",
    }
    data.update(overrides)
    return data


def deliver(type_: str, data: dict, occurred_at: str) -> None:
    event = new_event(type_, data, service="catalog")
    detail = {**event.to_detail(), "occurred_at": occurred_at}
    handle(eventbridge_event(detail, type_), None)


def test_event_published_creates_the_counter(bookings_table) -> None:
    deliver("EventPublished", snapshot("e1"), "2026-01-01T00:00:00+00:00")
    current = places.get("e1")
    assert (current.places_total, current.places_left, current.price_cents) == (10, 10, 2500)
    assert current.is_open


def test_event_updated_moves_places_left_by_the_delta(bookings_table) -> None:
    deliver("EventPublished", snapshot("e1"), "2026-01-01T00:00:00+00:00")
    # simulate 3 places already taken
    places.client().update_item(
        TableName=bookings_table,
        Key={"pk": {"S": "EVENT#e1"}, "sk": {"S": "PLACES"}},
        UpdateExpression="SET places_left = :l",
        ExpressionAttributeValues={":l": {"N": "7"}},
    )
    deliver(
        "EventUpdated", snapshot("e1", places=15, price_cents=3000), "2026-01-02T00:00:00+00:00"
    )
    current = places.get("e1")
    assert (current.places_total, current.places_left, current.price_cents) == (15, 12, 3000)


def test_stale_update_is_ignored(bookings_table) -> None:
    deliver("EventPublished", snapshot("e1"), "2026-01-01T00:00:00+00:00")
    deliver("EventUpdated", snapshot("e1", places=20), "2026-01-03T00:00:00+00:00")
    deliver("EventUpdated", snapshot("e1", places=5), "2026-01-02T00:00:00+00:00")  # late
    assert places.get("e1").places_total == 20


def test_redelivery_is_idempotent(bookings_table) -> None:
    for _ in range(3):
        deliver("EventPublished", snapshot("e1"), "2026-01-01T00:00:00+00:00")
    assert places.get("e1").places_left == 10


def test_event_cancelled_closes_booking(bookings_table) -> None:
    deliver("EventPublished", snapshot("e1"), "2026-01-01T00:00:00+00:00")
    deliver("EventCancelled", snapshot("e1", status="cancelled"), "2026-01-02T00:00:00+00:00")
    assert not places.get("e1").is_open
