"""Catalog domain: Event, Location and Event status.

Pure Python. No SQLAlchemy and no lbz in here; the repository maps to and from
persistence, and the API layer maps DomainError to HTTP. Vocabulary follows GLOSSARY.md.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from meeton_shared.errors import ConflictError, ValidationError

SUPPORTED_CURRENCIES = frozenset({"EUR", "CHF", "USD", "GBP"})
MAX_TITLE = 120
MAX_DESCRIPTION = 10_000
MAX_IMPORTANT_INFORMATION = 2_000


def utcnow() -> datetime:
    return datetime.now(UTC)


def _require_aware(value: datetime, name: str) -> datetime:
    if value.tzinfo is None:
        raise ValidationError(f"{name} must include a timezone", details={"field": name})
    return value.astimezone(UTC)


class EventStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CANCELLED = "cancelled"


# The only legal moves: Draft -> Published -> Cancelled.
ALLOWED_TRANSITIONS: dict[EventStatus, frozenset[EventStatus]] = {
    EventStatus.DRAFT: frozenset({EventStatus.PUBLISHED}),
    EventStatus.PUBLISHED: frozenset({EventStatus.CANCELLED}),
    EventStatus.CANCELLED: frozenset(),
}


class IllegalStatusTransition(ConflictError):
    pass


@dataclass(frozen=True)
class GeoPoint:
    lat: float
    lng: float

    def __post_init__(self) -> None:
        if not -90 <= self.lat <= 90:
            raise ValidationError("Latitude must be between -90 and 90", details={"field": "lat"})
        if not -180 <= self.lng <= 180:
            raise ValidationError(
                "Longitude must be between -180 and 180", details={"field": "lng"}
            )


@dataclass(frozen=True)
class Money:
    """Price in minor units (cents). Zero means the Event is free."""

    amount_cents: int
    currency: str = "EUR"

    def __post_init__(self) -> None:
        if self.amount_cents < 0:
            raise ValidationError("Price cannot be negative", details={"field": "price"})
        if self.currency not in SUPPORTED_CURRENCIES:
            raise ValidationError(
                f"Unsupported currency {self.currency}", details={"field": "currency"}
            )

    @property
    def is_free(self) -> bool:
        return self.amount_cents == 0


@dataclass(frozen=True)
class Location:
    """Where an Event happens. Visitors search for Events by Location."""

    name: str
    address: str
    city: str
    point: GeoPoint
    id: uuid.UUID = field(default_factory=uuid.uuid4)

    def __post_init__(self) -> None:
        for attr in ("name", "address", "city"):
            if not getattr(self, attr).strip():
                raise ValidationError(f"Location {attr} is required", details={"field": attr})


@dataclass
class Event:
    """Something that happens at one Location on a specific date and time."""

    organizer_id: str
    title: str
    description: str
    starts_at: datetime
    ends_at: datetime
    places: int
    price: Money
    location: Location
    important_information: str = ""
    cover_picture_key: str | None = None
    status: EventStatus = EventStatus.DRAFT
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)
    published_at: datetime | None = None
    cancelled_at: datetime | None = None

    def __post_init__(self) -> None:
        self.starts_at = _require_aware(self.starts_at, "starts_at")
        self.ends_at = _require_aware(self.ends_at, "ends_at")
        self._check_invariants()

    # --- invariants -------------------------------------------------------------
    def _check_invariants(self) -> None:
        title = self.title.strip()
        if not title:
            raise ValidationError("Title is required", details={"field": "title"})
        if len(title) > MAX_TITLE:
            raise ValidationError(f"Title is longer than {MAX_TITLE}", details={"field": "title"})
        if len(self.description) > MAX_DESCRIPTION:
            raise ValidationError("Description is too long", details={"field": "description"})
        if len(self.important_information) > MAX_IMPORTANT_INFORMATION:
            raise ValidationError(
                "Important information is too long", details={"field": "important_information"}
            )
        if self.ends_at <= self.starts_at:
            raise ValidationError("An Event must end after it starts", details={"field": "ends_at"})
        if self.places < 1:
            raise ValidationError("An Event needs at least one place", details={"field": "places"})
        if not self.organizer_id:
            raise ValidationError("Organizer is required", details={"field": "organizer_id"})

    # --- queries ----------------------------------------------------------------
    @property
    def is_draft(self) -> bool:
        return self.status is EventStatus.DRAFT

    @property
    def is_published(self) -> bool:
        return self.status is EventStatus.PUBLISHED

    @property
    def is_cancelled(self) -> bool:
        return self.status is EventStatus.CANCELLED

    def has_started(self, now: datetime | None = None) -> bool:
        return (now or utcnow()) >= self.starts_at

    # --- behaviour --------------------------------------------------------------
    def _transition(self, target: EventStatus) -> None:
        if target not in ALLOWED_TRANSITIONS[self.status]:
            raise IllegalStatusTransition(
                f"An Event cannot go from {self.status} to {target}",
                details={"status": str(self.status), "target": str(target)},
            )
        self.status = target

    def publish(self, now: datetime | None = None) -> None:
        now = now or utcnow()
        if self.has_started(now):
            raise ValidationError("Cannot publish an Event that has already started")
        self._transition(EventStatus.PUBLISHED)
        self.published_at = now
        self.updated_at = now

    def cancel(self, now: datetime | None = None) -> None:
        now = now or utcnow()
        self._transition(EventStatus.CANCELLED)
        self.cancelled_at = now
        self.updated_at = now

    EDITABLE = frozenset(
        {
            "title",
            "description",
            "important_information",
            "starts_at",
            "ends_at",
            "places",
            "price",
            "location",
            "cover_picture_key",
        }
    )

    def edit(self, now: datetime | None = None, **changes: Any) -> set[str]:
        """Apply changes atomically (all-or-nothing); returns the changed field names."""
        if self.is_cancelled:
            raise ConflictError("A Cancelled Event cannot be edited")
        unknown = set(changes) - self.EDITABLE
        if unknown:
            raise ValidationError(
                f"Cannot edit {sorted(unknown)}", details={"fields": sorted(unknown)}
            )
        changed = {k for k, v in changes.items() if getattr(self, k) != v}
        if not changed:
            return set()
        candidate = replace(self, **changes)  # re-runs __post_init__ invariants
        if self.is_published and "starts_at" in changed and candidate.has_started(now):
            raise ValidationError("A Published Event cannot be moved into the past")
        for name in changed:
            setattr(self, name, getattr(candidate, name))
        self.updated_at = now or utcnow()
        return changed
