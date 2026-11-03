"""Test helpers: build HTTP API (payload 1.0) events like API Gateway sends them."""

from __future__ import annotations

import json
import uuid
from typing import Any


def http_api_event(
    method: str,
    route: str,
    *,
    path_params: dict[str, str] | None = None,
    query: dict[str, str | list[str]] | None = None,
    body: Any = None,
    headers: dict[str, str] | None = None,
    claims: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """An API Gateway HTTP API event, payload format 1.0, with optional JWT claims."""
    path_params = path_params or {}
    path = route.format(**path_params)
    mv_query = {k: v if isinstance(v, list) else [v] for k, v in query.items()} if query else None
    hdrs = {"content-type": "application/json", **(headers or {})}
    authorizer = {"claims": claims, "scopes": None} if claims else None
    return {
        "version": "1.0",
        "resource": route,
        "path": path,
        "httpMethod": method,
        "headers": hdrs,
        "multiValueHeaders": {k: [v] for k, v in hdrs.items()},
        "queryStringParameters": {k: v[-1] for k, v in mv_query.items()} if mv_query else None,
        "multiValueQueryStringParameters": mv_query,
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "api",
            "authorizer": authorizer,
            "httpMethod": method,
            "path": path,
            "requestId": str(uuid.uuid4()),
            "resourcePath": route,
            "stage": "$default",
        },
        "pathParameters": path_params or None,
        "stageVariables": None,
        "body": json.dumps(body) if body is not None else None,
        "isBase64Encoded": False,
    }


def eventbridge_event(detail: dict[str, Any], detail_type: str) -> dict[str, Any]:
    return {
        "version": "0",
        "id": str(uuid.uuid4()),
        "detail-type": detail_type,
        "source": detail.get("source", "meeton.test"),
        "account": "123456789012",
        "time": "2026-01-01T00:00:00Z",
        "region": "eu-central-1",
        "resources": [],
        "detail": detail,
    }


class RecordingEventBridge:
    """Stands in for the EventBridge client; records every PutEvents entry."""

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def put_events(self, Entries: list[dict[str, Any]]) -> dict[str, Any]:
        self.entries.extend(Entries)
        return {"FailedEntryCount": 0, "Entries": [{"EventId": str(uuid.uuid4())} for _ in Entries]}

    @property
    def events(self) -> list[tuple[str, dict[str, Any]]]:
        """(detail-type, envelope) pairs in publish order."""
        return [(e["DetailType"], json.loads(e["Detail"])) for e in self.entries]

    def of_type(self, type_: str) -> list[dict[str, Any]]:
        return [detail["data"] for t, detail in self.events if t == type_]


def capture_lbz_events() -> RecordingEventBridge:
    """Route lbz's EventAPI (HTTP handlers) to a recorder. Undo with release_lbz_events()."""
    from lbz.aws_boto3 import client

    recorder = RecordingEventBridge()
    client.__dict__["eventbridge"] = recorder
    return recorder


def release_lbz_events() -> None:
    from lbz.aws_boto3 import client

    client.__dict__.pop("eventbridge", None)
