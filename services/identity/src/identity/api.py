"""Admin-only HTTP API over Cognito groups."""

from __future__ import annotations

from lbz.response import Response
from lbz.router import add_route

from identity import users
from localbini_shared.api import ApiResource, domain_errors, make_http_handler


class IdentityAdminResource(ApiResource):
    @add_route("/admin/users", method="GET")
    @domain_errors
    def list_users(self) -> Response:
        return Response(users.list_users(self.principal, self.query("search"), self.query("next")))

    @add_route("/admin/users/{username}/roles/{role}", method="PUT")
    @domain_errors
    def grant(self, username: str, role: str) -> Response:
        return Response(users.grant(self.principal, username, role))

    @add_route("/admin/users/{username}/roles/{role}", method="DELETE")
    @domain_errors
    def revoke(self, username: str, role: str) -> Response:
        return Response(users.revoke(self.principal, username, role))


handle = make_http_handler(IdentityAdminResource, "identity")
