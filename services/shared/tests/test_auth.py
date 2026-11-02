"""Visitor / Attendee / Organizer / Admin permutations for the shared auth helpers."""

import pytest
from localbini_shared.auth import (
    ANONYMOUS,
    Principal,
    Role,
    can_see_owned,
    parse_groups,
    principal_from_request_context,
    require_authenticated,
    require_owner_or_admin,
    require_role,
)
from localbini_shared.errors import ForbiddenError, UnauthenticatedError

VISITOR = ANONYMOUS
ATTENDEE = Principal(user_id="u-attendee", email="a@example.com")
ORGANIZER = Principal(user_id="u-org", roles=frozenset({"organizer"}))
OTHER_ORGANIZER = Principal(user_id="u-org-2", roles=frozenset({"organizer"}))
ADMIN = Principal(user_id="u-admin", roles=frozenset({"admin"}))


@pytest.mark.parametrize(
    ("principal", "expected"),
    [(VISITOR, UnauthenticatedError), (ATTENDEE, None), (ORGANIZER, None), (ADMIN, None)],
    ids=["visitor", "attendee", "organizer", "admin"],
)
def test_require_authenticated(principal, expected) -> None:
    if expected:
        with pytest.raises(expected):
            require_authenticated(principal)
    else:
        assert require_authenticated(principal) == principal.user_id


@pytest.mark.parametrize(
    ("principal", "expected"),
    [
        (VISITOR, UnauthenticatedError),
        (ATTENDEE, ForbiddenError),
        (ORGANIZER, None),
        (ADMIN, None),
    ],
    ids=["visitor", "attendee", "organizer", "admin"],
)
def test_require_organizer_role(principal, expected) -> None:
    if expected:
        with pytest.raises(expected):
            require_role(principal, Role.ORGANIZER)
    else:
        require_role(principal, Role.ORGANIZER)


@pytest.mark.parametrize(
    ("principal", "expected"),
    [
        (VISITOR, UnauthenticatedError),
        (ATTENDEE, ForbiddenError),
        (ORGANIZER, ForbiddenError),
        (ADMIN, None),
    ],
    ids=["visitor", "attendee", "organizer", "admin"],
)
def test_require_admin_role(principal, expected) -> None:
    if expected:
        with pytest.raises(expected):
            require_role(principal, Role.ADMIN)
    else:
        require_role(principal, Role.ADMIN)


def test_admin_does_not_pass_when_admin_passes_disabled() -> None:
    with pytest.raises(ForbiddenError):
        require_role(ADMIN, Role.ORGANIZER, admin_passes=False)


@pytest.mark.parametrize(
    ("principal", "expected"),
    [
        (VISITOR, UnauthenticatedError),
        (ATTENDEE, ForbiddenError),
        (OTHER_ORGANIZER, ForbiddenError),
        (ORGANIZER, None),
        (ADMIN, None),
    ],
    ids=["visitor", "attendee", "other-organizer", "owner", "admin"],
)
def test_owner_or_admin(principal, expected) -> None:
    if expected:
        with pytest.raises(expected):
            require_owner_or_admin(principal, owner_id="u-org", what="Events")
    else:
        require_owner_or_admin(principal, owner_id="u-org", what="Events")


def test_can_see_owned() -> None:
    assert can_see_owned(ORGANIZER, "u-org")
    assert can_see_owned(ADMIN, "u-org")
    assert not can_see_owned(OTHER_ORGANIZER, "u-org")
    assert not can_see_owned(VISITOR, "u-org")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, set()),
        ("", set()),
        (["admin", "organizer"], {"admin", "organizer"}),
        ("[admin organizer]", {"admin", "organizer"}),  # HTTP API flattens arrays like this
        ('["admin","organizer"]', {"admin", "organizer"}),
        ("organizer", {"organizer"}),
    ],
)
def test_parse_groups(raw, expected) -> None:
    assert parse_groups(raw) == expected


@pytest.mark.parametrize(
    "context",
    [
        {"authorizer": {"claims": {"sub": "u1", "cognito:groups": "[organizer]"}}},
        {"authorizer": {"jwt": {"claims": {"sub": "u1", "cognito:groups": ["organizer"]}}}},
    ],
    ids=["payload-1.0", "payload-2.0"],
)
def test_principal_from_both_payload_shapes(context) -> None:
    principal = principal_from_request_context(context)
    assert principal.user_id == "u1"
    assert principal.is_organizer
    assert not principal.is_admin


def test_missing_authorizer_is_anonymous() -> None:
    assert principal_from_request_context({}) is ANONYMOUS
    assert principal_from_request_context({"authorizer": None}) is ANONYMOUS
