from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("AWS_DEFAULT_REGION", "eu-central-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("EVENT_BUS_NAME", "localbini-test")


def _pg_available() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


@pytest.fixture(scope="session")
def migrated_engine() -> Iterator[object]:
    """A real Postgres/PostGIS database at head (docker compose up -d postgres)."""
    if not _pg_available():
        pytest.skip("DATABASE_URL not set (docker compose up -d postgres)")
    from catalog.db import get_engine
    from catalog.migrate import upgrade

    upgrade()
    yield get_engine()
