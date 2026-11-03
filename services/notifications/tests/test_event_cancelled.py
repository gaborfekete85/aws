"""Cancellation emails: concurrent (asyncio), bounded, rate-limited, retried on partial failure."""

import asyncio
import threading
import time

import pytest

from localbini_shared.events import new_event
from notifications import sender
from notifications.app import handle
from notifications.fanout import RateLimiter, fan_out

from .conftest import sqs_record


# --- fan_out / RateLimiter --------------------------------------------------------
def test_never_more_than_max_concurrency_in_flight() -> None:
    in_flight = peak = 0
    lock = threading.Lock()

    def send(_):
        nonlocal in_flight, peak
        with lock:
            in_flight += 1
            peak = max(peak, in_flight)
        time.sleep(0.02)
        with lock:
            in_flight -= 1
        return True

    limiter = RateLimiter(rate=10_000, burst=10_000)
    result = asyncio.run(fan_out(list(range(40)), send, max_concurrency=4, limiter=limiter))
    assert result.sent == 40
    assert 1 < peak <= 4  # concurrent, but bounded


def test_rate_limiter_spaces_out_sends_deterministically() -> None:
    now = 0.0
    slept = []

    def clock():
        return now

    async def fake_sleep(seconds):
        nonlocal now
        slept.append(seconds)
        now += seconds

    async def run():
        limiter = RateLimiter(rate=2, burst=1, clock=clock, sleep=fake_sleep)
        for _ in range(5):
            await limiter.acquire()

    asyncio.run(run())
    assert sum(slept) == pytest.approx(2.0)  # 5 sends at 2/s: first free, then 4 x 0.5 s


def test_rate_limit_holds_in_real_time() -> None:
    limiter = RateLimiter(rate=20, burst=1)
    start = time.monotonic()
    asyncio.run(fan_out(list(range(10)), lambda _: True, max_concurrency=10, limiter=limiter))
    assert time.monotonic() - start >= 0.4  # 9 waits of 50 ms


def test_failures_are_collected_and_everyone_else_is_sent() -> None:
    def send(i):
        if i == 3:
            raise RuntimeError("SES throttled")
        return True

    result = asyncio.run(
        fan_out(list(range(6)), send, max_concurrency=3, limiter=RateLimiter(rate=1000, burst=1000))
    )
    assert result.sent == 5
    assert [item for item, _ in result.failed] == [3]


# --- EventBookingsCancelled through the SQS entrypoint ----------------------------
def cancellation(n: int, *, missing_email_at: int | None = None) -> dict:
    return {
        "event": {
            "event_id": "evt-9",
            "title": "Sunset jazz",
            "starts_at": "2031-06-01T16:00:00+00:00",
            "location": {"name": "Seebad Enge", "city": "Zürich"},
        },
        "attendees": [
            {
                "booking_id": f"b{i}",
                "attendee_id": f"u{i}",
                "attendee_email": None if i == missing_email_at else f"u{i}@example.com",
                "places": 1 + i % 2,
                "was_confirmed": i % 2 == 0,
            }
            for i in range(n)
        ],
        "part": 1,
        "parts": 1,
    }


def deliver(data: dict, message_id: str = "m1"):
    event = new_event("EventBookingsCancelled", data, service="booking")
    return handle(
        {"Records": [sqs_record("EventBookingsCancelled", event.to_detail(), message_id)]}, None
    )


@pytest.fixture
def fast_ses(monkeypatch):
    monkeypatch.setenv("SES_MAX_SEND_RATE", "200")
    monkeypatch.setenv("SES_MAX_CONCURRENCY", "8")


def test_every_attendee_gets_one_email(aws, outbox, fast_ses) -> None:
    assert deliver(cancellation(12, missing_email_at=5)) == {"batchItemFailures": []}

    recipients = sorted(m.destinations["ToAddresses"][0] for m in outbox())
    assert len(recipients) == 11  # one Attendee had no email
    assert "u5@example.com" not in recipients
    sample = next(m for m in outbox() if m.destinations["ToAddresses"] == ["u0@example.com"])
    assert sample.subject == "Cancelled: Sunset jazz"
    assert "Sunday 1 June 2031, 18:00" in sample.body
    assert "refund" in sample.body  # u0 had a confirmed (paid) Booking


def test_partial_failure_fails_the_record_and_retry_sends_only_the_rest(
    aws, outbox, fast_ses, monkeypatch
) -> None:
    real_send = sender.send
    failing = {"u2@example.com", "u7@example.com"}

    def flaky(to, email):
        if to in failing:
            raise RuntimeError("Throttling: Maximum sending rate exceeded")
        return real_send(to, email)

    monkeypatch.setattr(sender, "send", flaky)
    assert deliver(cancellation(10), "m1") == {"batchItemFailures": [{"itemIdentifier": "m1"}]}
    assert len(outbox()) == 8

    failing.clear()  # SES recovers; SQS redelivers the same message
    assert deliver(cancellation(10), "m1") == {"batchItemFailures": []}
    recipients = [m.destinations["ToAddresses"][0] for m in outbox()]
    assert len(recipients) == 10
    assert len(set(recipients)) == 10  # nobody emailed twice


def test_redelivered_message_sends_nothing_new(aws, outbox, fast_ses) -> None:
    deliver(cancellation(4), "m1")
    deliver(cancellation(4), "m1")
    assert len(outbox()) == 4
