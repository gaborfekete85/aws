import json

from localbini_shared.health import handle
from localbini_shared.testing import http_api_event


def test_health_returns_ok_through_lambda_entrypoint() -> None:
    result = handle(http_api_event("GET", "/health"), None)

    assert result["statusCode"] == 200
    assert json.loads(result["body"])["status"] == "ok"
    assert result["headers"]["Access-Control-Allow-Methods"].startswith("GET")


def test_unknown_route_is_404() -> None:
    result = handle(http_api_event("GET", "/nope"), None)
    assert result["statusCode"] == 404


def test_wrong_method_is_405() -> None:
    result = handle(http_api_event("DELETE", "/health"), None)
    assert result["statusCode"] == 405


def test_handles_null_fields_sent_by_http_api() -> None:
    event = http_api_event("GET", "/health")
    del event["requestContext"]["resourcePath"]
    event["headers"] = None
    assert handle(event, None)["statusCode"] == 200


def test_security_headers_on_every_response() -> None:
    for event in (http_api_event("GET", "/health"), http_api_event("GET", "/nope")):
        headers = handle(event, None)["headers"]
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["Cache-Control"] == "no-store"
        assert headers["Strict-Transport-Security"].startswith("max-age=")
