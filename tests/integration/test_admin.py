"""Admin role API on the deployed environment: it must never be reachable without a token."""

import pytest

pytestmark = pytest.mark.dev


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/admin/users"),
        ("PUT", "/admin/users/someone/roles/organizer"),
        ("DELETE", "/admin/users/someone/roles/organizer"),
    ],
)
def test_admin_routes_require_a_jwt(http, method, path) -> None:
    response = http.request(method, path)
    assert response.status_code == 401  # rejected by the API Gateway JWT authorizer


def test_forged_token_is_rejected(http) -> None:
    response = http.get(
        "/admin/users", headers={"Authorization": "Bearer eyJhbGciOiJub25lIn0.e30."}
    )
    assert response.status_code == 401
