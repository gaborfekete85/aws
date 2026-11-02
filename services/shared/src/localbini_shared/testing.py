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
        "source": detail.get("source", "localbini.test"),
        "account": "123456789012",
        "time": "2026-01-01T00:00:00Z",
        "region": "eu-central-1",
        "resources": [],
        "detail": detail,
    }
