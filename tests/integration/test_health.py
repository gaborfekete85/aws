import pytest

pytestmark = pytest.mark.dev


def test_health_is_reachable_through_api_gateway(http) -> None:
    response = http.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["env"] in {"dev", "prod"}


def test_cors_preflight_is_answered(http) -> None:
    response = http.options(
        "/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code in {200, 204}
    assert "access-control-allow-origin" in response.headers
