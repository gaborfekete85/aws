"""Booking HTTP API (Lambdalizator)."""

from __future__ import annotations

from lbz.response import Response
from lbz.router import add_route
from localbini_shared.api import ApiResource, domain_errors, make_http_handler
from localbini_shared.events import register
from pydantic import BaseModel, ConfigDict, Field

from booking import service
from booking.domain import MAX_PLACES_PER_BOOKING


class BookingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    places: int = Field(ge=1, le=MAX_PLACES_PER_BOOKING)


class BookingResource(ApiResource):
    @add_route("/events/{event_id}/bookings", method="POST")
    @domain_errors
    def request_booking(self, event_id: str) -> Response:
        data = self.body_as(BookingRequest)
        booking, events = service.request_booking(self.principal, event_id, data.places)
        for domain_event in events:
            register(domain_event)
        return Response(booking.to_dict(), status_code=201)

    @add_route("/me/bookings", method="GET")
    @domain_errors
    def my_bookings(self) -> Response:
        return Response({"items": [b.to_dict() for b in service.my_bookings(self.principal)]})

    @add_route("/bookings/{booking_id}", method="GET")
    @domain_errors
    def get_booking(self, booking_id: str) -> Response:
        return Response(service.get_booking(self.principal, booking_id).to_dict())

    @add_route("/events/{event_id}/availability", method="GET")
    @domain_errors
    def availability(self, event_id: str) -> Response:
        return Response(service.availability(event_id))


handle = make_http_handler(BookingResource, "booking")
