"""Booking domain: an Attendee's reservation of one or more Places at an Event."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from localbini_shared.errors import ConflictError, ValidationError

from booking.table import BOOKING_SK, attendee_gsi, booking_pk, event_pk

MAX_PLACES_PER_BOOKING = 10


def utcnow() -> datetime:
    return datetime.now(UTC)


class BookingStatus(StrEnum):
    PENDING = "pending"  # Hold placed, waiting for payment
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"  # Event cancelled
    EXPIRED = "expired"  # Hold ran out before payment
    NEEDS_ATTENTION = "needs_attention"  # paid after the Hold expired (manual handling)


@dataclass
class Booking:
    event_id: str
    attendee_id: str
    places: int
    amount_cents: int
    currency: str
    attendee_email: str | None = None
    status: BookingStatus = BookingStatus.PENDING
    booking_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=utcnow)
    hold_expires_at: datetime | None = None
    confirmed_at: datetime | None = None
    cancelled_at: datetime | None = None
    event_title: str = ""

    def __post_init__(self) -> None:
        if not 1 <= self.places <= MAX_PLACES_PER_BOOKING:
            raise ValidationError(
                f"A Booking takes 1 to {MAX_PLACES_PER_BOOKING} places",
                details={"field": "places"},
            )

    @classmethod
    def request(
        cls,
        *,
        event_id: str,
        attendee_id: str,
        attendee_email: str | None,
        places: int,
        unit_price_cents: int,
        currency: str,
        hold_minutes: int,
        event_title: str = "",
        now: datetime | None = None,
    ) -> Booking:
        now = now or utcnow()
        return cls(
            event_id=event_id,
            attendee_id=attendee_id,
            attendee_email=attendee_email,
            places=places,
            amount_cents=unit_price_cents * places,
            currency=currency,
            created_at=now,
            hold_expires_at=now + timedelta(minutes=hold_minutes),
            event_title=event_title,
        )

    @property
    def is_free(self) -> bool:
        return self.amount_cents == 0

    def confirm(self, now: datetime | None = None) -> None:
        if self.status is not BookingStatus.PENDING:
            raise ConflictError(f"A {self.status} Booking cannot be confirmed")
        self.status = BookingStatus.CONFIRMED
        self.confirmed_at = now or utcnow()

    # --- persistence --------------------------------------------------------------
    def to_item(self) -> dict[str, Any]:
        created = self.created_at.isoformat()
        item: dict[str, Any] = {
            "pk": {"S": booking_pk(self.booking_id)},
            "sk": {"S": BOOKING_SK},
            "gsi1pk": {"S": attendee_gsi(self.attendee_id)},
            "gsi1sk": {"S": created},
            "gsi2pk": {"S": event_pk(self.event_id)},
            "gsi2sk": {"S": created},
            "type": {"S": "Booking"},
            "booking_id": {"S": self.booking_id},
            "event_id": {"S": self.event_id},
            "event_title": {"S": self.event_title},
            "attendee_id": {"S": self.attendee_id},
            "places": {"N": str(self.places)},
            "amount_cents": {"N": str(self.amount_cents)},
            "currency": {"S": self.currency},
            "status": {"S": str(self.status)},
            "created_at": {"S": created},
        }
        if self.attendee_email:
            item["attendee_email"] = {"S": self.attendee_email}
        for name in ("hold_expires_at", "confirmed_at", "cancelled_at"):
            value = getattr(self, name)
            if value is not None:
                item[name] = {"S": value.isoformat()}
        return item

    @classmethod
    def from_item(cls, item: dict[str, Any]) -> Booking:
        def ts(name: str) -> datetime | None:
            return datetime.fromisoformat(item[name]["S"]) if name in item else None

        booking = cls.__new__(cls)
        booking.__dict__.update(
            booking_id=item["booking_id"]["S"],
            event_id=item["event_id"]["S"],
            event_title=item.get("event_title", {}).get("S", ""),
            attendee_id=item["attendee_id"]["S"],
            attendee_email=item.get("attendee_email", {}).get("S"),
            places=int(item["places"]["N"]),
            amount_cents=int(item["amount_cents"]["N"]),
            currency=item["currency"]["S"],
            status=BookingStatus(item["status"]["S"]),
            created_at=datetime.fromisoformat(item["created_at"]["S"]),
            hold_expires_at=ts("hold_expires_at"),
            confirmed_at=ts("confirmed_at"),
            cancelled_at=ts("cancelled_at"),
        )
        return booking

    def to_dict(self) -> dict[str, Any]:
        return {
            "booking_id": self.booking_id,
            "event_id": self.event_id,
            "event_title": self.event_title,
            "places": self.places,
            "amount_cents": self.amount_cents,
            "currency": self.currency,
            "status": str(self.status),
            "created_at": self.created_at.isoformat(),
            "hold_expires_at": self.hold_expires_at.isoformat() if self.hold_expires_at else None,
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
        }
