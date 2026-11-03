import json

import pytest

from localbini_shared.events import DomainEvent, EventPublisher, PublishError, new_event
from localbini_shared.logging import bind_request
from localbini_shared.testing import eventbridge_event


def test_envelope_round_trips_through_eventbridge_shape() -> None:
    event = new_event("EventPublished", {"event_id": "e1", "places": 10}, service="catalog")
    parsed = DomainEvent.from_eventbridge(eventbridge_event(event.to_detail(), event.type))
    assert parsed == event
    assert parsed.source == "localbini.catalog"


def test_envelope_parses_string_detail_from_sqs() -> None:
    event = new_event("BookingConfirmed", {"booking_id": "b1"}, service="booking")
    raw = {"detail-type": event.type, "detail": json.dumps(event.to_detail())}
    assert DomainEvent.from_eventbridge(raw) == event


def test_new_event_carries_correlation_id() -> None:
    bind_request("req-1", "corr-1")
    assert new_event("X", {}, service="s").correlation_id == "corr-1"


def test_publisher_puts_events_in_batches(bus) -> None:
    publisher = EventPublisher("localbini-test", client=bus)
    events = [new_event("Ping", {"i": i}, service="test") for i in range(23)]
    assert publisher.publish(events) == []


class _FailingClient:
    def put_events(self, Entries):
        return {"Entries": [{"ErrorCode": "Boom"} for _ in Entries]}


def test_publisher_raises_with_failed_events() -> None:
    publisher = EventPublisher("bus", client=_FailingClient())
    with pytest.raises(PublishError) as info:
        publisher.publish([new_event("Ping", {}, service="t")])
    assert len(info.value.failed) == 1
