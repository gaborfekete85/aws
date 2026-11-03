"""Run Alembic migrations.

Deployed as the in-VPC ``catalog-migrate`` Lambda (CI invokes it after
``terraform apply``) and usable locally: ``uv run python -m catalog.migrate``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from localbini_shared.logging import configure_logging, get_logger
from sqlalchemy import text

from catalog.db import get_engine

logger = get_logger(__name__)

MIGRATIONS = Path(__file__).parent / "migrations"


def alembic_config() -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS))
    return cfg


def upgrade(revision: str = "head") -> str | None:
    engine = get_engine()
    with engine.begin() as conn:
        cfg = alembic_config()
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, revision)
        current: str | None = conn.execute(text("select version_num from alembic_version")).scalar()
    logger.info("migrations applied", extra={"revision": current})
    return current


def handle(event: dict[str, Any], context: Any) -> dict[str, Any]:
    configure_logging("catalog-migrate")
    revision = upgrade(event.get("revision", "head") if isinstance(event, dict) else "head")
    return {"status": "ok", "revision": revision}


if __name__ == "__main__":
    configure_logging("catalog-migrate")
    print(upgrade())
