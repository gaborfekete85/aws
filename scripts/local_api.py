"""Local API: the real Catalog + Booking Lambda handlers behind an aiohttp server.

For offline development and for verifying tests/smoke/load.py:

    docker compose up -d
    DATABASE_URL=postgresql+psycopg://meeton:meeton@localhost:5432/catalog \\
    DYNAMODB_ENDPOINT_URL=http://localhost:8000 \\
      uv run python scripts/local_api.py --port 4010

- **Real concurrency**: handlers run in a *process* pool (lbz keeps per-process
  singletons), so concurrent Bookings really race on DynamoDB Local.
- **Local event bus**: events a handler publishes are captured in the worker and
  delivered to the Booking consumer, so publishing an Event feeds its Places counter.
- **Fake authorizer**: accepts the web app's fake tokens (``fake-token.<base64 JSON user>``),
  or ``Bearer local:<sub>[:organizer|admin]``, and enforces JWT on non-public routes
  like API Gateway does. Never use outside local development.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import re
import uuid
from concurrent.futures import ProcessPoolExecutor
from typing import Any

from aiohttp import web

# (method, route template, handler, public) mirroring infra/modules/stack routes
ROUTES: list[tuple[str, str, str, bool]] = [
    ("GET", "/health", "meeton_shared.health:handle", True),
    ("GET", "/events", "catalog.api:handle", True),
    ("GET", "/events/{event_id}", "catalog.api:handle", True),
    ("POST", "/events", "catalog.api:handle", False),
    ("PATCH", "/events/{event_id}", "catalog.api:handle", False),
    ("POST", "/events/{event_id}/publish", "catalog.api:handle", False),
    ("POST", "/events/{event_id}/cancel", "catalog.api:handle", False),
    ("GET", "/organizer/events", "catalog.api:handle", False),
    ("GET", "/organizer/events/{event_id}", "catalog.api:handle", False),
    ("GET", "/events/{event_id}/availability", "booking.api:handle", True),
    ("POST", "/events/{event_id}/bookings", "booking.api:handle", False),
    ("GET", "/me/bookings", "booking.api:handle", False),
    ("GET", "/bookings/{booking_id}", "booking.api:handle", False),
]
CONSUMERS = {
    "EventPublished": "booking.consumers:handle",
    "EventUpdated": "booking.consumers:handle",
    "EventCancelled": "booking.consumers:handle",
}


def _compile(template: str) -> re.Pattern[str]:
    return re.compile("^" + re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", template) + "$")


COMPILED = [(m, _compile(t), t, h, p) for m, t, h, p in ROUTES]


# --- worker process ----------------------------------------------------------------
def _worker_init() -> None:
    os.environ.setdefault("EVENT_BUS_NAME", "meeton-local")
    os.environ.setdefault("BOOKINGS_TABLE", "meeton-local-bookings")
    os.environ.setdefault("AWS_DEFAULT_REGION", "eu-central-1")
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "local")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "local")
    os.environ.setdefault("CORS_ORIGINS", "*")
    from meeton_shared import testing

    testing.capture_lbz_events()  # lbz PutEvents -> in-process recorder


def _invoke(handler_ref: str, event: dict[str, Any]) -> tuple[Any, list[dict[str, Any]]]:
    """Run one Lambda handler; return its result and the events it published."""
    import importlib

    from lbz.aws_boto3 import client

    from meeton_shared import events as shared_events

    recorder = client.__dict__["eventbridge"]
    recorder.entries.clear()
    published: list[dict[str, Any]] = []

    original = shared_events.EventPublisher.__init__

    def capture_publisher(self: Any, bus_name: str | None = None, client_: Any = None) -> None:
        original(self, bus_name or "meeton-local", client_ or recorder)

    shared_events.EventPublisher.__init__ = capture_publisher  # type: ignore[method-assign]
    try:
        module_name, attr = handler_ref.split(":")
        result = getattr(importlib.import_module(module_name), attr)(event, None)
    finally:
        shared_events.EventPublisher.__init__ = original  # type: ignore[method-assign]
    published = list(recorder.entries)
    return result, published


# --- HTTP server ---------------------------------------------------------------------
def _claims(header: str | None) -> dict[str, Any] | None:
    if not header or not header.startswith("Bearer "):
        return None
    token = header.removeprefix("Bearer ").strip()
    if token.startswith("fake-token."):
        user = json.loads(base64.b64decode(token.removeprefix("fake-token.")))
        return {
            "sub": user["sub"],
            "email": user.get("email"),
            "cognito:groups": f"[{' '.join(user.get('groups', []))}]",
        }
    if token.startswith("local:"):
        _, sub, *role = token.split(":")
        return {"sub": sub, "email": f"{sub}@local.test", "cognito:groups": f"[{' '.join(role)}]"}
    return None


def _cors(response: web.StreamResponse) -> web.StreamResponse:
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "authorization, content-type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
    return response


class LocalApi:
    def __init__(self, workers: int) -> None:
        self.pool = ProcessPoolExecutor(max_workers=workers, initializer=_worker_init)

    async def run(self, handler: str, event: dict[str, Any]) -> Any:
        loop = asyncio.get_running_loop()
        result, published = await loop.run_in_executor(self.pool, _invoke, handler, event)
        for entry in published:  # the local event bus
            consumer = CONSUMERS.get(entry["DetailType"])
            if consumer:
                eb_event = {
                    "id": str(uuid.uuid4()),
                    "detail-type": entry["DetailType"],
                    "source": entry["Source"],
                    "detail": json.loads(entry["Detail"]),
                }
                await self.run(consumer, eb_event)
        return result

    async def handle(self, request: web.Request) -> web.StreamResponse:
        if request.method == "OPTIONS":
            return _cors(web.Response(status=204))
        for method, pattern, template, handler, public in COMPILED:
            match = pattern.match(request.path)
            if method != request.method or not match:
                continue
            claims = _claims(request.headers.get("Authorization"))
            if not public and claims is None:
                return _cors(web.json_response({"message": "Unauthorized"}, status=401))
            from meeton_shared.testing import http_api_event

            query = {k: request.query.getall(k) for k in request.query}
            event = http_api_event(
                method,
                template,
                path_params=match.groupdict(),
                query=query or None,
                claims=claims,
            )
            event["body"] = await request.text() or None
            result = await self.run(handler, event)
            response = web.Response(
                status=result["statusCode"], body=result["body"], content_type="application/json"
            )
            return _cors(response)
        return _cors(web.json_response({"message": "Not found"}, status=404))


def ensure_bookings_table() -> None:
    os.environ.setdefault("AWS_DEFAULT_REGION", "eu-central-1")
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "local")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "local")
    from booking import table

    name = os.environ.setdefault("BOOKINGS_TABLE", "meeton-local-bookings")
    if name not in table.client().list_tables()["TableNames"]:
        table.client().create_table(**table.table_definition(name))


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Meeton API (development only)")
    parser.add_argument("--port", type=int, default=4010)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    from catalog.migrate import upgrade

    upgrade()
    ensure_bookings_table()
    api = LocalApi(args.workers)
    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", api.handle)
    web.run_app(app, port=args.port)


if __name__ == "__main__":
    main()
