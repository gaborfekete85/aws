"""Alembic environment: uses the connection handed in by catalog.migrate, or builds one."""

from __future__ import annotations

from alembic import context
from catalog.db import get_engine
from sqlalchemy import Connection

target_metadata = None
try:  # the ORM metadata exists once the domain model is defined
    from catalog.models import Base

    target_metadata = Base.metadata
except ImportError:  # pragma: no cover
    pass


def include_object(
    obj: object, name: str | None, type_: str, reflected: bool, compare_to: object
) -> bool:
    """Only compare tables we model (PostGIS/TIGER ship their own tables)."""
    if type_ == "table" and target_metadata is not None:
        return name in target_metadata.tables
    return True


def run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        include_object=lambda obj, name, type_, reflected, compare_to: (
            not (
                type_ == "table" and name == "spatial_ref_sys"  # owned by PostGIS
            )
        ),
    )
    with context.begin_transaction():
        context.run_migrations()


connection = context.config.attributes.get("connection")
if connection is not None:
    run(connection)
else:
    with get_engine().begin() as conn:
        run(conn)
