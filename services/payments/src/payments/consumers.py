"""Payments' bus consumers."""

from __future__ import annotations

from meeton_shared.consumers import make_event_handler
from meeton_shared.events import DomainEvent
from payments.checkout import on_booking_requested, on_hold_expired


def booking_requested(event: DomainEvent) -> None:
    on_booking_requested(event.data)


def hold_expired(event: DomainEvent) -> None:
    on_hold_expired(event.data)


HANDLERS = {"BookingRequested": [booking_requested], "HoldExpired": [hold_expired]}

handle = make_event_handler(HANDLERS, "payments-consumer")
