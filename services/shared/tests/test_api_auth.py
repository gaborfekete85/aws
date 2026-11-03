import json

from lbz.response import Response
from lbz.router import add_route

from localbini_shared.api import ApiResource, domain_errors, make_http_handler
from localbini_shared.auth import Role, require_role
from localbini_shared.testing import http_api_event


class WhoAmIResource(ApiResource):
    @add_route("/whoami", method="GET")
    def whoami(self) -> Response:
        p = self.principal
        return Response({"user_id": p.user_id, "roles": sorted(p.roles)})

    @add_route("/organizer-only", method="GET")
    @domain_errors
    def organizer_only(self) -> Response:
        require_role(self.principal, Role.ORGANIZER)
        return Response({"ok": True})


handle = make_http_handler(WhoAmIResource, "whoami")


def test_principal_comes_from_authorizer_claims() -> None:
    event = http_api_event(
        "GET", "/whoami", claims={"sub": "u1", "cognito:groups": "[organizer admin]"}
    )
    body = json.loads(handle(event, None)["body"])
    assert body == {"user_id": "u1", "roles": ["admin", "organizer"]}


def test_public_route_without_token_is_anonymous() -> None:
    body = json.loads(handle(http_api_event("GET", "/whoami"), None)["body"])
    assert body == {"user_id": None, "roles": []}


def test_role_check_maps_to_401_and_403() -> None:
    assert handle(http_api_event("GET", "/organizer-only"), None)["statusCode"] == 401
    attendee = http_api_event("GET", "/organizer-only", claims={"sub": "u1"})
    assert handle(attendee, None)["statusCode"] == 403
    organizer = http_api_event(
        "GET", "/organizer-only", claims={"sub": "u1", "cognito:groups": "[organizer]"}
    )
    assert handle(organizer, None)["statusCode"] == 200
