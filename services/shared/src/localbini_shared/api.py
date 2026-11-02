"""lbz application skeleton: base resource with error mapping, logging and event sending."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any

from lbz.events.api import EventAPI
from lbz.exceptions import BadRequestError, UnprocessableEntity
from lbz.resource import CORSResource
from lbz.response import Response
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from localbini_shared.errors import DomainError, to_http_error
from localbini_shared.logging import bind_request, configure_logging, get_logger

logger = get_logger(__name__)

# lbz reads its own variable names; derive them from ours so deployments only set EVENT_BUS_NAME.
os.environ.setdefault("EVENTS_BUS_NAME", os.environ.get("EVENT_BUS_NAME", ""))
os.environ.setdefault("AWS_LAMBDA_FUNCTION_NAME", os.environ.get("SERVICE_NAME", "localbini"))

ALLOWED_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]


def normalize_http_api_event(event: dict[str, Any]) -> dict[str, Any]:
    """Make an HTTP API (payload 1.0) event look like what lbz expects.

    HTTP APIs omit some REST-API fields or set them to null.
    """
    event = dict(event)
    ctx = dict(event.get("requestContext") or {})
    ctx.setdefault("resourcePath", event.get("resource"))
    ctx.setdefault("httpMethod", event.get("httpMethod"))
    ctx.setdefault("requestId", ctx.get("requestId") or "local")
    event["requestContext"] = ctx
    event.setdefault("path", event.get("resource"))
    event["stageVariables"] = event.get("stageVariables") or {}
    event.setdefault("body", None)
    event.setdefault("multiValueQueryStringParameters", None)
    event["headers"] = event.get("headers") or {}
    return event


class ApiResource(CORSResource):
    """Base resource for every Localbini HTTP API.

    - domain errors are mapped to HTTP errors
    - domain events registered during the request are sent only on success
    """

    def __init__(self, event: dict[str, Any]) -> None:
        origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
        super().__init__(event, methods=ALLOWED_METHODS, origins=origins or ["*"])
        EventAPI().clear()

    def __call__(self) -> Response:
        response = super().__call__()
        response.headers.update(self.resp_headers())
        return response

    def post_request_hook(self) -> None:
        api = EventAPI()
        if self.response is not None and self.response.ok:
            api.send()
            if api.failed_events:
                logger.error(
                    "some domain events were not published",
                    extra={"failed": [e.type for e in api.failed_events]},
                )
        else:
            api.clear_pending()

    def body_as[M: BaseModel](self, model: type[M]) -> M:
        """Parse the JSON body into a pydantic model (422 on invalid input)."""
        raw = self.request.json_body
        if raw is None:
            raise BadRequestError("A JSON body is required")
        try:
            return model.model_validate(raw)
        except PydanticValidationError as error:
            raise UnprocessableEntity(
                message="Invalid request body",
                extra={"errors": json.loads(error.json(include_url=False, include_input=False))},
            ) from error

    def query(self, name: str, default: str | None = None) -> str | None:
        try:
            value: str = self.request.query_params[name]
            return value
        except KeyError:
            return default


def domain_errors[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    """Decorator for endpoint methods: translate DomainError into lbz HTTP errors."""

    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return fn(*args, **kwargs)
        except DomainError as error:
            raise to_http_error(error) from error

    wrapped.__name__ = fn.__name__
    wrapped.__doc__ = fn.__doc__
    return wrapped


def json_response(body: dict[str, Any] | list[Any], status: int = 200) -> Response:
    payload: dict[str, Any] = body if isinstance(body, dict) else {"items": body}
    return Response(payload, status_code=status)


def make_http_handler(
    resource_cls: type[ApiResource], service: str
) -> Callable[[dict[str, Any], Any], dict[str, Any]]:
    """Build the Lambda entrypoint for an HTTP API resource."""
    configure_logging(service)

    def handle(event: dict[str, Any], context: Any) -> dict[str, Any]:
        event = normalize_http_api_event(event)
        headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
        bind_request(event["requestContext"]["requestId"], headers.get("x-correlation-id"))
        result: dict[str, Any] = resource_cls(event)().to_dict()
        return result

    return handle
