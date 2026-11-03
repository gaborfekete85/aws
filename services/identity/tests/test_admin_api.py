"""Admin role management against a moto Cognito user pool, through the lbz handler."""

import json
import os

import pytest

os.environ.setdefault("AWS_DEFAULT_REGION", "eu-central-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("EVENT_BUS_NAME", "meeton-test")

from identity import users
from identity.api import handle
from meeton_shared.testing import http_api_event

ADMIN = {"sub": "admin-sub", "cognito:groups": "[admin]"}
ORGANIZER = {"sub": "org-sub", "cognito:groups": "[organizer]"}
ATTENDEE = {"sub": "user-sub"}


@pytest.fixture
def pool(monkeypatch):
    from moto import mock_aws

    users.cognito.cache_clear()
    with mock_aws():
        client = users.cognito()
        pool_id = client.create_user_pool(PoolName="test", UsernameAttributes=["email"])[
            "UserPool"
        ]["Id"]
        monkeypatch.setenv("USER_POOL_ID", pool_id)
        for group in ("admin", "organizer"):
            client.create_group(UserPoolId=pool_id, GroupName=group)
        for email, name in [
            ("ada@example.com", "Ada"),
            ("bob@example.com", "Bob"),
            ("olga@example.com", "Olga"),
        ]:
            client.admin_create_user(
                UserPoolId=pool_id,
                Username=email,
                UserAttributes=[{"Name": "email", "Value": email}, {"Name": "name", "Value": name}],
            )
        client.admin_add_user_to_group(
            UserPoolId=pool_id, Username="olga@example.com", GroupName="organizer"
        )
        yield client
    users.cognito.cache_clear()


def call(method, route, claims, path=None, query=None):
    result = handle(
        http_api_event(method, route, path_params=path, claims=claims, query=query), None
    )
    return result["statusCode"], json.loads(result["body"])


def username_of(email: str) -> str:
    _, body = call("GET", "/admin/users", ADMIN, query={"search": email})
    return body["items"][0]["username"]


def test_admin_lists_users_with_roles(pool) -> None:
    status, body = call("GET", "/admin/users", ADMIN)
    assert status == 200
    roles = {u["email"]: u["roles"] for u in body["items"]}
    assert roles == {
        "ada@example.com": [],
        "bob@example.com": [],
        "olga@example.com": ["organizer"],
    }


def test_search_by_email_prefix(pool) -> None:
    _, body = call("GET", "/admin/users", ADMIN, query={"search": "bo"})
    assert [u["email"] for u in body["items"]] == ["bob@example.com"]


def test_admin_grants_and_revokes_organizer(pool) -> None:
    ada = username_of("ada@example.com")
    path = {"username": ada, "role": "organizer"}

    status, body = call("PUT", "/admin/users/{username}/roles/{role}", ADMIN, path)
    assert (status, body["roles"]) == (200, ["organizer"])
    status, body = call("PUT", "/admin/users/{username}/roles/{role}", ADMIN, path)  # idempotent
    assert (status, body["roles"]) == (200, ["organizer"])

    status, body = call("DELETE", "/admin/users/{username}/roles/{role}", ADMIN, path)
    assert (status, body["roles"]) == (200, [])


@pytest.mark.parametrize(("claims", "status"), [(None, 401), (ATTENDEE, 403), (ORGANIZER, 403)])
def test_non_admins_are_refused(pool, claims, status) -> None:
    assert call("GET", "/admin/users", claims)[0] == status
    path = {"username": "whoever", "role": "organizer"}
    assert call("PUT", "/admin/users/{username}/roles/{role}", claims, path)[0] == status
    assert call("DELETE", "/admin/users/{username}/roles/{role}", claims, path)[0] == status


def test_admin_role_cannot_be_granted_through_the_api(pool) -> None:
    path = {"username": username_of("ada@example.com"), "role": "admin"}
    status, body = call("PUT", "/admin/users/{username}/roles/{role}", ADMIN, path)
    assert status == 422
    assert body["field"] == "role"


def test_unknown_user_is_404(pool) -> None:
    path = {"username": "nobody", "role": "organizer"}
    assert call("PUT", "/admin/users/{username}/roles/{role}", ADMIN, path)[0] == 404


def test_search_value_is_escaped(pool) -> None:
    status, body = call("GET", "/admin/users", ADMIN, query={"search": 'x" or email ^= "'})
    assert status == 200
    assert body["items"] == []
