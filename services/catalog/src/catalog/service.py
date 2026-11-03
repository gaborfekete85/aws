"""Application service for Organizers managing their Events.

Each method is one use case: load, check authorization, call the domain, save,
and record the domain events to publish once the transaction has committed.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from catalog.domain import Event, EventStatus, Money
from catalog.events import event_cancelled, event_published, event_updated
from catalog.geocoding import Geocoder
from catalog.locations import LocationInput, location_changed, resolve_location
from catalog.repository import EventRepository
from catalog.schemas import EventCreate, EventUpdate
from meeton_shared.auth import Principal, Role, require_owner_or_admin, require_role
from meeton_shared.errors import ForbiddenError, NotFoundError, ValidationError
from meeton_shared.events import DomainEvent


def parse_event_id(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as error:
        raise NotFoundError("Event not found") from error


class OrganizerEvents:
    def __init__(self, repo: EventRepository, geocoder: Geocoder) -> None:
        self.repo = repo
        self.geocoder = geocoder
        self.outbox: list[DomainEvent] = []

    # --- commands -------------------------------------------------------------
    def create(self, principal: Principal, data: EventCreate) -> Event:
        require_role(principal, Role.ORGANIZER)
        assert principal.user_id is not None
        location = resolve_location(LocationInput(**data.location.model_dump()), self.geocoder)
        event = Event(
            organizer_id=principal.user_id,
            title=data.title,
            description=data.description,
            important_information=data.important_information,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
            places=data.places,
            price=Money(data.price_cents, data.currency.upper()),
            location=location,
        )
        self.repo.add(event)
        return event

    def edit(self, principal: Principal, event_id: uuid.UUID, data: EventUpdate) -> Event:
        event = self._load_for_management(principal, event_id)
        changes: dict[str, Any] = data.model_dump(exclude_unset=True, exclude={"location"})
        if "price_cents" in changes or "currency" in changes:
            changes["price"] = Money(
                changes.pop("price_cents", event.price.amount_cents),
                str(changes.pop("currency", event.price.currency)).upper(),
            )
        if data.location is not None:
            loc_in = LocationInput(**data.location.model_dump())
            if location_changed(event.location, loc_in):
                changes["location"] = resolve_location(loc_in, self.geocoder)
        changes = {k: v for k, v in changes.items() if v is not None}
        changed = event.edit(**changes)
        if changed:
            self.repo.save(event)
            if event.is_published:
                self.outbox.append(event_updated(event, changed))
        return event

    def publish(self, principal: Principal, event_id: uuid.UUID) -> Event:
        event = self._load_for_management(principal, event_id)
        event.publish()
        self.repo.save(event)
        self.outbox.append(event_published(event))
        return event

    def cancel(self, principal: Principal, event_id: uuid.UUID) -> Event:
        event = self._load_for_management(principal, event_id)
        event.cancel()
        self.repo.save(event)
        self.outbox.append(event_cancelled(event))
        return event

    def set_cover_picture(self, principal: Principal, event_id: uuid.UUID, key: str) -> Event:
        event = self._load_for_management(principal, event_id)
        if not key.startswith(f"covers/{event.id}/"):
            raise ValidationError("Cover picture key does not belong to this Event")
        changed = event.edit(cover_picture_key=key)
        if changed:
            self.repo.save(event)
            if event.is_published:
                self.outbox.append(event_updated(event, changed))
        return event

    # --- queries --------------------------------------------------------------
    def get(self, principal: Principal, event_id: uuid.UUID) -> Event:
        return self._load_for_management(principal, event_id)

    def list_mine(
        self,
        principal: Principal,
        status: EventStatus | None = None,
        organizer_id: str | None = None,
    ) -> Sequence[Event]:
        require_role(principal, Role.ORGANIZER)
        owner = principal.user_id
        if organizer_id and organizer_id != owner:
            if not principal.is_admin:
                raise ForbiddenError("Only Admins can list another Organizer's Events")
            owner = organizer_id
        assert owner is not None
        return self.repo.list_by_organizer(owner, status)

    # --- helpers --------------------------------------------------------------
    def _load_for_management(self, principal: Principal, event_id: uuid.UUID) -> Event:
        require_role(principal, Role.ORGANIZER)
        event = self.repo.get(event_id)
        require_owner_or_admin(principal, event.organizer_id, what="Events")
        return event
