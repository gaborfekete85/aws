"""Who is calling, and may they do this?

API Gateway's JWT authorizer has already verified the Cognito ID token's signature,
issuer, audience and expiry on protected routes. Services only read the claims and
apply domain authorization (roles and ownership) here, as defence in depth.

Roles (GLOSSARY): a **Visitor** is anyone (possibly anonymous); an **Attendee** is
any logged-in user; **Organizer** and **Admin** come from Cognito groups.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from localbini_shared.errors import ForbiddenError, UnauthenticatedError


class Role(StrEnum):
    ADMIN = "admin"
    ORGANIZER = "organizer"


@dataclass(frozen=True)
class Principal:
    user_id: str | None = None
    email: str | None = None
    name: str | None = None
    roles: frozenset[str] = field(default_factory=frozenset)

    @property
    def is_authenticated(self) -> bool:
        return self.user_id is not None

    @property
    def is_admin(self) -> bool:
        return Role.ADMIN in self.roles

    @property
    def is_organizer(self) -> bool:
        return Role.ORGANIZER in self.roles

    def has_role(self, role: Role | str) -> bool:
        return str(role) in self.roles


ANONYMOUS = Principal()


def parse_groups(raw: Any) -> frozenset[str]:
    """`cognito:groups` arrives as a list, a JSON-ish string, or "[a b]" from HTTP APIs."""
    if raw is None or raw == "":
        return frozenset()
    if isinstance(raw, list | tuple | set | frozenset):
        return frozenset(str(g) for g in raw)
    text = str(raw).strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    parts = text.replace(",", " ").replace('"', " ").split()
    return frozenset(p for p in parts if p)


def _claims_from_context(request_context: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    authorizer = (request_context or {}).get("authorizer") or {}
    # payload 2.0 / some 1.0 events: authorizer.jwt.claims ; payload 1.0: authorizer.claims
    jwt = authorizer.get("jwt") or {}
    claims = jwt.get("claims") or authorizer.get("claims")
    return claims if isinstance(claims, Mapping) else None


def principal_from_claims(claims: Mapping[str, Any] | None) -> Principal:
    if not claims or not claims.get("sub"):
        return ANONYMOUS
    return Principal(
        user_id=str(claims["sub"]),
        email=claims.get("email"),
        name=claims.get("name") or claims.get("cognito:username"),
        roles=parse_groups(claims.get("cognito:groups")),
    )


def principal_from_request_context(request_context: Mapping[str, Any] | None) -> Principal:
    return principal_from_claims(_claims_from_context(request_context))


# --- checks -------------------------------------------------------------------


def require_authenticated(principal: Principal) -> str:
    """Any logged-in user (an Attendee-to-be). Returns the user id."""
    if principal.user_id is None:
        raise UnauthenticatedError("You need to log in to do this")
    return principal.user_id


def require_role(principal: Principal, *roles: Role, admin_passes: bool = True) -> None:
    """Caller must hold one of `roles`. Admins pass every role check unless told otherwise."""
    require_authenticated(principal)
    if admin_passes and principal.is_admin:
        return
    if not any(principal.has_role(r) for r in roles):
        wanted = " or ".join(str(r) for r in roles)
        raise ForbiddenError(f"This needs the {wanted} role")


def require_owner_or_admin(principal: Principal, owner_id: str, *, what: str = "resource") -> None:
    """Organizers manage only their own Events; Admins can manage any."""
    require_authenticated(principal)
    if principal.is_admin or principal.user_id == owner_id:
        return
    raise ForbiddenError(f"You can only manage your own {what}")


def can_see_owned(principal: Principal, owner_id: str) -> bool:
    return principal.is_admin or (principal.user_id is not None and principal.user_id == owner_id)


def roles_of(principal: Principal) -> Iterable[str]:
    return sorted(principal.roles)
