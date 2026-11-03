import pytest
from sqlalchemy import text

from catalog.migrate import alembic_config


def test_migration_chain_is_linear_and_starts_with_postgis() -> None:
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(alembic_config())
    heads = script.get_heads()
    assert len(heads) == 1, f"multiple heads: {heads}"
    base = next(iter(script.get_bases()))
    assert base == "0001"
    assert script.get_current_head() == heads[0]


@pytest.mark.integration
def test_upgrade_enables_postgis(migrated_engine) -> None:
    with migrated_engine.connect() as conn:
        version = conn.execute(text("select postgis_version()")).scalar()
    assert version


@pytest.mark.integration
def test_upgrade_is_idempotent(migrated_engine) -> None:
    from catalog.migrate import upgrade

    assert upgrade() == upgrade()
