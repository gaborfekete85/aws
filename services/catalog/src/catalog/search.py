"""Public Event search: Published Events near a point, within a date range.

Served by PostGIS: ``ST_DWithin`` on a ``geography`` column backed by a GiST
index (ADR-0001: no OpenSearch).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from geoalchemy2 import Geography
from localbini_shared.errors import ValidationError
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from catalog.domain import Event, EventStatus, utcnow
from catalog.models import EventRow, LocationRow
from catalog.repository import event_from_row

MAX_RADIUS_KM = 200.0
DEFAULT_RADIUS_KM = 25.0
MAX_LIMIT = 50
DEFAULT_LIMIT = 20


@dataclass(frozen=True)
class SearchQuery:
    lat: float | None = None
    lng: float | None = None
    radius_km: float = DEFAULT_RADIUS_KM
    starts_from: datetime | None = None  # inclusive; defaults to now
    starts_to: datetime | None = None  # inclusive
    limit: int = DEFAULT_LIMIT
    offset: int = 0

    def __post_init__(self) -> None:
        if (self.lat is None) != (self.lng is None):
            raise ValidationError("Give both lat and lng, or neither", details={"field": "lat"})
        if self.lat is not None and not -90 <= self.lat <= 90:
            raise ValidationError("lat out of range", details={"field": "lat"})
        if self.lng is not None and not -180 <= self.lng <= 180:
            raise ValidationError("lng out of range", details={"field": "lng"})
        if not 0 < self.radius_km <= MAX_RADIUS_KM:
            raise ValidationError(
                f"radius_km must be between 0 and {MAX_RADIUS_KM:g}",
                details={"field": "radius_km"},
            )
        if not 1 <= self.limit <= MAX_LIMIT:
            raise ValidationError(f"limit must be 1..{MAX_LIMIT}", details={"field": "limit"})
        if self.offset < 0:
            raise ValidationError("offset must be >= 0", details={"field": "offset"})
        if self.starts_from and self.starts_to and self.starts_to < self.starts_from:
            raise ValidationError("'to' is before 'from'", details={"field": "to"})

    @property
    def is_geo(self) -> bool:
        return self.lat is not None


@dataclass(frozen=True)
class SearchHit:
    event: Event
    distance_km: float | None


@dataclass(frozen=True)
class SearchPage:
    hits: list[SearchHit]
    total: int
    limit: int
    offset: int

    @property
    def next_offset(self) -> int | None:
        nxt = self.offset + self.limit
        return nxt if nxt < self.total else None


def search_published(session: Session, query: SearchQuery) -> SearchPage:
    starts_from = query.starts_from or utcnow()
    conditions = [EventRow.status == str(EventStatus.PUBLISHED), EventRow.starts_at >= starts_from]
    if query.starts_to is not None:
        conditions.append(EventRow.starts_at <= query.starts_to)

    distance = None
    if query.is_geo:
        origin = cast(
            func.ST_SetSRID(func.ST_MakePoint(query.lng, query.lat), 4326), Geography(srid=4326)
        )
        conditions.append(func.ST_DWithin(LocationRow.point, origin, query.radius_km * 1000.0))
        distance = (func.ST_Distance(LocationRow.point, origin) / 1000.0).label("distance_km")

    base = (
        select(EventRow.id)
        .join(LocationRow, EventRow.location_id == LocationRow.id)
        .where(*conditions)
    )
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0

    columns = [EventRow] if distance is None else [EventRow, distance]
    stmt = (
        select(*columns)
        .join(LocationRow, EventRow.location_id == LocationRow.id)
        .where(*conditions)
        .order_by(EventRow.starts_at, EventRow.id)
        .limit(query.limit)
        .offset(query.offset)
    )
    hits: list[SearchHit] = []
    for row in session.execute(stmt).unique():
        km = float(row[1]) if distance is not None else None
        hits.append(SearchHit(event_from_row(row[0]), round(km, 3) if km is not None else None))
    return SearchPage(hits=hits, total=total, limit=query.limit, offset=query.offset)


def get_public(session: Session, event: Event) -> Event:
    """Visitors may see Published and Cancelled Events (Attendees learn about cancellations)."""
    from localbini_shared.errors import NotFoundError

    if event.is_draft:
        raise NotFoundError("Event not found")
    return event
