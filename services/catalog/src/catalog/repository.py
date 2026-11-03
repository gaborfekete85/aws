"""Event repository: the only place that knows how Events are stored."""

from __future__ import annotations

import struct
import uuid
from collections.abc import Sequence

from geoalchemy2.elements import WKBElement, WKTElement
from sqlalchemy import select
from sqlalchemy.orm import Session

from catalog.domain import Event, EventStatus, GeoPoint, Location, Money
from catalog.models import EventRow, LocationRow
from meeton_shared.errors import NotFoundError


def _point_to_db(point: GeoPoint) -> object:
    return WKTElement(f"POINT({point.lng!r} {point.lat!r})", srid=4326)


_SRID_FLAG = 0x20000000


def parse_ewkb_point(data: bytes) -> tuple[float, float]:
    """(x, y) of a 2D (E)WKB Point.

    Replaces shapely, which pulled numpy (~53 MB) into the Catalog Lambda just for this.
    Layout: byte order (1) | type (uint32, SRID flag 0x20000000) | [srid] | x | y (doubles).
    """
    order = "<" if data[0] == 1 else ">"
    (geom_type,) = struct.unpack_from(f"{order}I", data, 1)
    if geom_type & 0xFF != 1:
        raise ValueError(f"not a Point (WKB type {geom_type:#x})")
    offset = 9 if geom_type & _SRID_FLAG else 5
    x, y = struct.unpack_from(f"{order}dd", data, offset)
    return x, y


def _point_from_db(value: object) -> GeoPoint:
    raw = value.data if isinstance(value, WKBElement) else value
    data = bytes.fromhex(raw) if isinstance(raw, str) else bytes(raw)  # type: ignore[arg-type]
    lng, lat = parse_ewkb_point(data)
    return GeoPoint(lat=lat, lng=lng)


def location_from_row(row: LocationRow) -> Location:
    return Location(
        id=row.id,
        name=row.name,
        address=row.address,
        city=row.city,
        point=_point_from_db(row.point),
    )


def event_from_row(row: EventRow) -> Event:
    event = Event.__new__(Event)  # rows are already valid; skip re-validation on load
    event.__dict__.update(
        id=row.id,
        organizer_id=row.organizer_id,
        title=row.title,
        description=row.description,
        important_information=row.important_information,
        cover_picture_key=row.cover_picture_key,
        starts_at=row.starts_at,
        ends_at=row.ends_at,
        places=row.places,
        price=Money(row.price_cents, row.currency),
        location=location_from_row(row.location),
        status=EventStatus(row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
        published_at=row.published_at,
        cancelled_at=row.cancelled_at,
    )
    return event


def _apply(event: Event, row: EventRow, location_row: LocationRow) -> None:
    loc = event.location
    location_row.id = loc.id
    location_row.name = loc.name
    location_row.address = loc.address
    location_row.city = loc.city
    location_row.point = _point_to_db(loc.point)
    row.id = event.id
    row.organizer_id = event.organizer_id
    row.title = event.title
    row.description = event.description
    row.important_information = event.important_information
    row.cover_picture_key = event.cover_picture_key
    row.starts_at = event.starts_at
    row.ends_at = event.ends_at
    row.places = event.places
    row.price_cents = event.price.amount_cents
    row.currency = event.price.currency
    row.status = str(event.status)
    row.location = location_row
    row.created_at = event.created_at
    row.updated_at = event.updated_at
    row.published_at = event.published_at
    row.cancelled_at = event.cancelled_at


class EventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, event: Event) -> None:
        self.session.add(self._to_row(event, EventRow(), LocationRow()))
        self.session.flush()

    def save(self, event: Event) -> None:
        row = self.session.get(EventRow, event.id)
        if row is None:
            raise NotFoundError("Event not found")
        location_row = row.location
        if location_row.id != event.location.id:
            location_row = self.session.get(LocationRow, event.location.id) or LocationRow()
        self._to_row(event, row, location_row)
        self.session.flush()

    def get(self, event_id: uuid.UUID) -> Event:
        row = self.session.get(EventRow, event_id)
        if row is None:
            raise NotFoundError("Event not found", details={"event_id": str(event_id)})
        return event_from_row(row)

    def list_by_organizer(
        self, organizer_id: str, status: EventStatus | None = None
    ) -> Sequence[Event]:
        stmt = select(EventRow).where(EventRow.organizer_id == organizer_id)
        if status is not None:
            stmt = stmt.where(EventRow.status == str(status))
        stmt = stmt.order_by(EventRow.starts_at)
        return [event_from_row(r) for r in self.session.scalars(stmt).unique()]

    @staticmethod
    def _to_row(event: Event, row: EventRow, location_row: LocationRow) -> EventRow:
        _apply(event, row, location_row)
        return row
