import pytest
from lbz.exceptions import Conflict, NotFound, PermissionDenied, Unauthorized, UnprocessableEntity

from localbini_shared.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthenticatedError,
    ValidationError,
    to_http_error,
)


@pytest.mark.parametrize(
    ("domain", "http", "status"),
    [
        (ValidationError, UnprocessableEntity, 422),
        (NotFoundError, NotFound, 404),
        (ConflictError, Conflict, 409),
        (ForbiddenError, PermissionDenied, 403),
        (UnauthenticatedError, Unauthorized, 401),
    ],
)
def test_domain_errors_map_to_http(domain, http, status) -> None:
    mapped = to_http_error(domain("boom", details={"field": "x"}))
    assert isinstance(mapped, http)
    assert mapped.status_code == status
    assert mapped.message == "boom"
    assert mapped.extra == {"field": "x"}


def test_subclass_of_domain_error_uses_parent_mapping() -> None:
    class PlacesExhausted(ConflictError):
        pass

    assert isinstance(to_http_error(PlacesExhausted("full")), Conflict)
