"""Cognito user administration, restricted to what Admins need.

Only the ``organizer`` role is assignable here. ``admin`` stays a deliberate,
manual grant (see infra/modules/cognito/README.md) so a compromised Admin
session cannot mint more Admins.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import cache
from typing import Any

import boto3
from botocore.exceptions import ClientError

from localbini_shared.auth import Principal, Role, require_role
from localbini_shared.errors import NotFoundError, ValidationError

ASSIGNABLE_ROLES = frozenset({Role.ORGANIZER})
PAGE_SIZE = 25


@cache
def cognito() -> Any:
    return boto3.client("cognito-idp")


def pool_id() -> str:
    return os.environ["USER_POOL_ID"]


@dataclass(frozen=True)
class UserSummary:
    username: str
    sub: str
    email: str
    name: str
    enabled: bool
    status: str
    roles: list[str]

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _members(group: str) -> set[str]:
    members: set[str] = set()
    kwargs: dict[str, Any] = {"UserPoolId": pool_id(), "GroupName": group}
    while True:
        page = cognito().list_users_in_group(**kwargs)
        members.update(u["Username"] for u in page["Users"])
        if "NextToken" not in page:
            return members
        kwargs["NextToken"] = page["NextToken"]


def _summary(user: dict[str, Any], organizers: set[str], admins: set[str]) -> UserSummary:
    attrs = {a["Name"]: a["Value"] for a in user.get("Attributes", [])}
    username = user["Username"]
    roles = [
        r for r, members in (("admin", admins), ("organizer", organizers)) if username in members
    ]
    return UserSummary(
        username=username,
        sub=attrs.get("sub", username),
        email=attrs.get("email", ""),
        name=attrs.get("name", ""),
        enabled=bool(user.get("Enabled", True)),
        status=user.get("UserStatus", ""),
        roles=roles,
    )


def _escape_filter(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def list_users(
    principal: Principal, search: str | None = None, next_token: str | None = None
) -> dict[str, Any]:
    require_role(principal, Role.ADMIN, admin_passes=False)
    kwargs: dict[str, Any] = {"UserPoolId": pool_id(), "Limit": PAGE_SIZE}
    if search:
        kwargs["Filter"] = f'email ^= "{_escape_filter(search.strip())}"'
    if next_token:
        kwargs["PaginationToken"] = next_token
    page = cognito().list_users(**kwargs)
    organizers, admins = _members("organizer"), _members("admin")
    return {
        "items": [_summary(u, organizers, admins).to_dict() for u in page["Users"]],
        "next_token": page.get("PaginationToken"),
    }


def _check_role(role: str) -> None:
    if role not in ASSIGNABLE_ROLES:
        raise ValidationError(
            f"Only these roles can be assigned here: {sorted(ASSIGNABLE_ROLES)}",
            details={"field": "role"},
        )


def _change(principal: Principal, username: str, role: str, add: bool) -> dict[str, Any]:
    require_role(principal, Role.ADMIN, admin_passes=False)
    _check_role(role)
    call = cognito().admin_add_user_to_group if add else cognito().admin_remove_user_from_group
    try:
        call(UserPoolId=pool_id(), Username=username, GroupName=role)
        user = cognito().admin_get_user(UserPoolId=pool_id(), Username=username)
    except ClientError as error:
        if error.response["Error"]["Code"] == "UserNotFoundException":
            raise NotFoundError("User not found", details={"username": username}) from error
        raise
    user["Attributes"] = user.get("UserAttributes", [])
    return _summary(user, _members("organizer"), _members("admin")).to_dict()


def grant(principal: Principal, username: str, role: str) -> dict[str, Any]:
    """Idempotent: granting a role the user already has is a no-op."""
    return _change(principal, username, role, add=True)


def revoke(principal: Principal, username: str, role: str) -> dict[str, Any]:
    """Idempotent: revoking a role the user does not have is a no-op."""
    return _change(principal, username, role, add=False)
