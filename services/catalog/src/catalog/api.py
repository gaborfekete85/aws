"""Catalog HTTP API (Lambdalizator). One Lambda serves every Catalog route."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time
from typing import Any, ClassVar
from zoneinfo import ZoneInfo

from lbz.response import Response
from lbz.router import add_route
from sqlalchemy.orm import Session

from catalog.db import session_factory
from catalog.domain import EventStatus
from catalog.geocoding import Geocoder, NominatimGeocoder
from catalog.media import CoverPictures
from catalog.repository import EventRepository
from catalog.schemas import CoverAttach, CoverUploadRequest, EventCreate, EventUpdate, event_out
from catalog.search import SearchPage, SearchQuery, get_public, search_published
from catalog.service import OrganizerEvents, parse_event_id
from localbini_shared.api import ApiResource, domain_errors, make_http_handler
from localbini_shared.errors import ValidationError
from localbini_shared.events import register


def _default_session() -> Session:
    return session_factory()()


class CatalogResource(ApiResource):
    # Seams for tests; production uses RDS and Nominatim.
    session_provider: ClassVar[Callable[[], Session]] = staticmethod(_default_session)
    geocoder_provider: ClassVar[Callable[[], Geocoder]] = staticmethod(NominatimGeocoder)
    covers_provider: ClassVar[Callable[[], CoverPictures]] = staticmethod(CoverPictures)

    @classmethod
    def cover_url_for(cls, key: str | None) -> str | None:
        return cls.covers_provider().url_for(key)

    def _organizer_events(self, session: Session) -> OrganizerEvents:
        return OrganizerEvents(EventRepository(session), type(self).geocoder_provider())

    def _run(self, use_case: Callable[[OrganizerEvents], Any], status: int = 200) -> Response:
        """Run a use case in one transaction; publish its domain events after commit."""
        session = type(self).session_provider()
        try:
            service = self._organizer_events(session)
            result = use_case(service)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
        for domain_event in service.outbox:
            register(domain_event)  # sent by ApiResource only when the response is OK
        return Response(self._render(result), status_code=status)

    def _render(self, result: Any) -> dict[str, Any]:
        cover = type(self).cover_url_for
        if isinstance(result, list | tuple):
            return {"items": [event_out(e, cover(e.cover_picture_key)) for e in result]}
        return event_out(result, cover(result.cover_picture_key))

    # --- Organizer endpoints --------------------------------------------------
    @add_route("/events", method="POST")
    @domain_errors
    def create_event(self) -> Response:
        data = self.body_as(EventCreate)
        return self._run(lambda s: s.create(self.principal, data), status=201)

    @add_route("/events/{event_id}", method="PATCH")
    @domain_errors
    def edit_event(self, event_id: str) -> Response:
        data = self.body_as(EventUpdate)
        eid = parse_event_id(event_id)
        return self._run(lambda s: s.edit(self.principal, eid, data))

    @add_route("/events/{event_id}/publish", method="POST")
    @domain_errors
    def publish_event(self, event_id: str) -> Response:
        eid = parse_event_id(event_id)
        return self._run(lambda s: s.publish(self.principal, eid))

    @add_route("/events/{event_id}/cancel", method="POST")
    @domain_errors
    def cancel_event(self, event_id: str) -> Response:
        eid = parse_event_id(event_id)
        return self._run(lambda s: s.cancel(self.principal, eid))

    @add_route("/events/{event_id}/cover-picture/upload-url", method="POST")
    @domain_errors
    def cover_upload_url(self, event_id: str) -> Response:
        data = self.body_as(CoverUploadRequest)
        eid = parse_event_id(event_id)
        self._run(lambda s: s.get(self.principal, eid))  # owner / Admin only
        ticket = (
            type(self).covers_provider().new_upload(eid, data.content_type, data.content_length)
        )
        return Response(
            {
                "key": ticket.key,
                "upload_url": ticket.upload_url,
                "method": "PUT",
                "headers": ticket.headers,
                "expires_in": ticket.expires_in,
                "max_bytes": ticket.max_bytes,
            },
            status_code=201,
        )

    @add_route("/events/{event_id}/cover-picture", method="PUT")
    @domain_errors
    def attach_cover_picture(self, event_id: str) -> Response:
        data = self.body_as(CoverAttach)
        eid = parse_event_id(event_id)
        self._run(lambda s: s.get(self.principal, eid))  # authorize before touching S3
        type(self).covers_provider().verify_uploaded(data.key)
        return self._run(lambda s: s.set_cover_picture(self.principal, eid, data.key))

    @add_route("/organizer/events", method="GET")
    @domain_errors
    def list_my_events(self) -> Response:
        raw_status = self.query("status")
        try:
            status = EventStatus(raw_status) if raw_status else None
        except ValueError as error:
            raise ValidationError(f"Unknown status {raw_status}") from error
        organizer_id = self.query("organizer_id")
        return self._run(lambda s: list(s.list_mine(self.principal, status, organizer_id)))

    @add_route("/organizer/events/{event_id}", method="GET")
    @domain_errors
    def get_my_event(self, event_id: str) -> Response:
        eid = parse_event_id(event_id)
        return self._run(lambda s: s.get(self.principal, eid))

    # --- public endpoints (no JWT) --------------------------------------------
    @add_route("/events", method="GET")
    @domain_errors
    def search_events(self) -> Response:
        query = self._search_query()
        session = type(self).session_provider()
        try:
            page = search_published(session, query)
        finally:
            session.close()
        return Response(self._render_page(page))

    @add_route("/events/{event_id}", method="GET")
    @domain_errors
    def get_event(self, event_id: str) -> Response:
        eid = parse_event_id(event_id)
        session = type(self).session_provider()
        try:
            event = get_public(session, EventRepository(session).get(eid))
        finally:
            session.close()
        return Response(event_out(event, type(self).cover_url_for(event.cover_picture_key)))

    def _search_query(self) -> SearchQuery:
        return SearchQuery(
            lat=self._number("lat", float),
            lng=self._number("lng", float),
            radius_km=_default(self._number("radius_km", float), 25.0),
            starts_from=_parse_bound(self.query("from"), "from", end_of_day=False),
            starts_to=_parse_bound(self.query("to"), "to", end_of_day=True),
            limit=int(_default(self._number("limit", int), 20)),
            offset=int(_default(self._number("offset", int), 0)),
        )

    def _number(self, name: str, kind: type[float] | type[int]) -> float | None:
        raw = self.query(name)
        if raw is None or raw == "":
            return None
        try:
            return kind(raw)
        except ValueError as error:
            raise ValidationError(f"{name} must be a number", details={"field": name}) from error

    def _render_page(self, page: SearchPage) -> dict[str, Any]:
        cover = type(self).cover_url_for
        items = []
        for hit in page.hits:
            item = event_out(hit.event, cover(hit.event.cover_picture_key))
            item["distance_km"] = hit.distance_km
            items.append(item)
        return {
            "items": items,
            "count": page.total,
            "limit": page.limit,
            "offset": page.offset,
            "next_offset": page.next_offset,
        }


SEARCH_TZ = ZoneInfo("Europe/Zurich")


def _default(value: float | None, default: float) -> float:
    return default if value is None else value


def _parse_bound(raw: str | None, name: str, *, end_of_day: bool) -> datetime | None:
    """Accept a date (2026-11-03, local day boundaries) or a full ISO-8601 datetime."""
    if not raw:
        return None
    try:
        if len(raw) == 10:
            day = date.fromisoformat(raw)
            return datetime.combine(day, time.max if end_of_day else time.min, SEARCH_TZ)
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValidationError(
            f"{name} must be a date or ISO datetime", details={"field": name}
        ) from error
    if value.tzinfo is None:
        value = value.replace(tzinfo=SEARCH_TZ)
    return value


handle = make_http_handler(CatalogResource, "catalog")
