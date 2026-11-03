"""Domain errors and their mapping to HTTP errors.

Domain code raises these; the API layer maps them to lbz exceptions so the
domain never imports web concerns.
"""

from __future__ import annotations

from typing import Any

from lbz.exceptions import (
    BadRequestError,
    Conflict,
    LambdaFWException,
    NotFound,
    PermissionDenied,
    Unauthorized,
    UnprocessableEntity,
)


class DomainError(Exception):
    """Base class for business-rule violations."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(DomainError):
    """Input is malformed or breaks an invariant."""


class NotFoundError(DomainError):
    """The requested aggregate does not exist (or is not visible to the caller)."""


class ConflictError(DomainError):
    """The request conflicts with the aggregate's current state."""


class ForbiddenError(DomainError):
    """The caller is authenticated but may not do this."""


class UnauthenticatedError(DomainError):
    """The caller must log in."""


_MAPPING: dict[type[DomainError], type[LambdaFWException]] = {
    ValidationError: UnprocessableEntity,
    NotFoundError: NotFound,
    ConflictError: Conflict,
    ForbiddenError: PermissionDenied,
    UnauthenticatedError: Unauthorized,
}


def to_http_error(error: DomainError) -> LambdaFWException:
    for domain_cls in type(error).__mro__:
        if domain_cls in _MAPPING:
            http_cls = _MAPPING[domain_cls]
            return http_cls(message=error.message, extra=error.details or None)
    return BadRequestError(message=error.message, extra=error.details or None)
