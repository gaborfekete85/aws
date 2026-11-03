"""The hand-written Alembic migrations must match the ORM models exactly."""

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from catalog.models import Base

pytestmark = pytest.mark.integration


def test_no_drift_between_models_and_migrations(migrated_engine) -> None:
    with migrated_engine.connect() as conn:
        ctx = MigrationContext.configure(
            conn,
            opts={
                "compare_type": True,
                # PostGIS / TIGER geocoder ship their own tables; compare only ours.
                "include_object": lambda obj, name, type_, reflected, compare_to: (
                    type_ != "table" or name in Base.metadata.tables
                ),
            },
        )
        diff = compare_metadata(ctx, Base.metadata)
    assert diff == []
