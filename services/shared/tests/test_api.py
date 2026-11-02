import json

from lbz.events import EventAPI
from lbz.response import Response
from lbz.router import add_route
from localbini_shared.api import ApiResource, domain_errors, make_http_handler
from localbini_shared.errors import ConflictError
from localbini_shared.events import new_event, register
from localbini_shared.testing import http_api_event
from pydantic import BaseModel


class Payload(BaseModel):
    name: str
    places: int


class DemoResource(ApiResource):
    @add_route("/demo", method="POST")
    @domain_errors
    def create(self) -> Response:
        body = self.body_as(Payload)
        register(new_event("DemoCreated", body.model_dump(), service="demo"))
        if body.places == 0:
            raise ConflictError("no places", details={"places": 0})
        return Response({"ok": True}, status_code=201)


handle = make_http_handler(DemoResource, "demo")


def test_valid_body_returns_201_and_sends_event(bus) -> None:
    result = handle(http_api_event("POST", "/demo", body={"name": "a", "places": 2}), None)
    assert result["statusCode"] == 201
    assert [e.type for e in EventAPI().sent_events] == ["DemoCreated"]


def test_invalid_body_is_422_with_field_errors() -> None:
    result = handle(http_api_event("POST", "/demo", body={"name": "a"}), None)
    assert result["statusCode"] == 422
    assert json.loads(result["body"])["errors"][0]["loc"] == ["places"]


def test_domain_error_maps_to_409_and_drops_pending_events(bus) -> None:
    result = handle(http_api_event("POST", "/demo", body={"name": "a", "places": 0}), None)
    assert result["statusCode"] == 409
    assert json.loads(result["body"])["places"] == 0
    assert EventAPI().sent_events == []
    assert EventAPI().pending_events == []


def test_missing_body_is_400() -> None:
    result = handle(http_api_event("POST", "/demo"), None)
    assert result["statusCode"] == 400
