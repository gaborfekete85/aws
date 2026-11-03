"""Catalog HTTP API (Lambdalizator). One Lambda serves every Catalog route."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

from lbz.response import Response
from lbz.router import add_route
from localbini_shared.api import ApiResource, domain_errors, make_http_handler
from localbini_shared.errors import ValidationError
from localbini_shared.events import register
from sqlalchemy.orm import Session

from catalog.db import session_factory
from catalog.domain import EventStatus
from catalog.geocoding import Geocoder, NominatimGeocoder
from catalog.repository import EventRepository
from catalog.schemas import EventCreate, EventUpdate, event_out
from catalog.service import OrganizerEvents, parse_event_id


def _default_session() -> Session:
    return session_factory()()


class CatalogResource(ApiResource):
    # Seams for tests; production uses RDS and Nominatim.
    session_provider: ClassVar[Callable[[], Session]] = staticmethod(_default_session)
    geocoder_provider: ClassVar[Callable[[], Geocoder]] = staticmethod(NominatimGeocoder)
    cover_url_for: ClassVar[Callable[[str | None], str | None]] = staticmethod(lambda key: None)

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


handle = make_http_handler(CatalogResource, "catalog")
