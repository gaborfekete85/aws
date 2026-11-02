"""`GET /health`: proves the API Gateway → Lambda → lbz path end to end."""

from __future__ import annotations

import os

from lbz.response import Response
from lbz.router import add_route

from localbini_shared.api import ApiResource, make_http_handler


class HealthResource(ApiResource):
    @add_route("/health", method="GET")
    def health(self) -> Response:
        return Response(
            {
                "status": "ok",
                "service": os.environ.get("SERVICE_NAME", "localbini"),
                "env": os.environ.get("ENV", "local"),
                "version": os.environ.get("APP_VERSION", "dev"),
            }
        )


handle = make_http_handler(HealthResource, "health")
