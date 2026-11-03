"""BookingConfirmed → one confirmation email, even on redelivery."""

from meeton_shared.events import new_event
from notifications.app import handle

from .conftest import sqs_record

CONFIRMED = {
    "booking_id": "b-42",
    "event_id": "e-1",
    "attendee_id": "ada",
    "attendee_email": "ada@example.com",
    "places": 2,
    "amount_cents": 5000,
    "currency": "CHF",
    "event_title": "Sunset jazz",
    "event": {
        "title": "Sunset jazz <live>",
        "starts_at": "2031-06-01T16:00:00+00:00",
        "location": {"name": "Seebad Enge", "address": "Mythenquai 9", "city": "Zürich"},
        "important_information": "Bring a blanket.\nNo dogs.",
    },
}


def deliver(data: dict, message_id: str = "m1"):
    event = new_event("BookingConfirmed", data, service="booking")
    return handle(
        {"Records": [sqs_record("BookingConfirmed", event.to_detail(), message_id)]}, None
    )


def test_sends_confirmation_with_event_details(aws, outbox) -> None:
    assert deliver(CONFIRMED) == {"batchItemFailures": []}

    [message] = outbox()
    assert message.destinations["ToAddresses"] == ["ada@example.com"]
    assert message.subject == "Your Booking for Sunset jazz <live> is confirmed"
    body = message.body
    assert "Sunset jazz &lt;live&gt;" in body  # escaped in HTML
    assert "Sunday 1 June 2031, 18:00" in body
    assert "Seebad Enge, Mythenquai 9, Zürich" in body
    assert "CHF 50.00" in body
    assert "Bring a blanket." in body
    assert "b-42" in body


def test_redelivery_does_not_send_twice(aws, outbox) -> None:
    deliver(CONFIRMED, "m1")
    deliver(CONFIRMED, "m1-redelivered")
    event = new_event("BookingConfirmed", CONFIRMED, service="booking")
    handle({"Records": [sqs_record("BookingConfirmed", event.to_detail(), "m2")]}, None)
    assert len(outbox()) == 1


def test_free_booking_says_free(aws, outbox) -> None:
    deliver({**CONFIRMED, "booking_id": "b-free", "amount_cents": 0})
    assert "Free" in outbox()[0].body


def test_without_important_information_the_section_is_omitted(aws, outbox) -> None:
    data = {**CONFIRMED, "event": {**CONFIRMED["event"], "important_information": ""}}
    deliver(data)
    assert "Important information" not in outbox()[0].body


def test_missing_email_is_skipped_not_retried(aws, outbox) -> None:
    assert deliver({**CONFIRMED, "attendee_email": None}) == {"batchItemFailures": []}
    assert outbox() == []


def test_ses_failure_is_retried_via_the_queue(aws, outbox, monkeypatch) -> None:
    from notifications import sender

    real = sender.send

    def flaky(*args, **kwargs):
        raise RuntimeError("Throttling")

    monkeypatch.setattr(sender, "send", flaky)
    assert deliver(CONFIRMED, "m1") == {"batchItemFailures": [{"itemIdentifier": "m1"}]}
    monkeypatch.setattr(sender, "send", real)
    assert deliver(CONFIRMED, "m1") == {"batchItemFailures": []}  # redelivered by SQS
    assert len(outbox()) == 1
