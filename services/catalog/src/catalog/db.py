"""Database engine for the Catalog (PostgreSQL + PostGIS on RDS).

Connection settings come from, in order:
1. ``DATABASE_URL`` (local dev, CI, tests), or
2. ``DB_HOST`` / ``DB_NAME`` / ``DB_SECRET_ARN`` (Lambda): the RDS-managed
   Secrets Manager secret holds ``username`` and ``password``.
"""

from __future__ import annotations

import json
import os
from functools import cache
from typing import Any

import boto3
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker


def _url_from_secret() -> URL:
    secret_arn = os.environ["DB_SECRET_ARN"]
    client: Any = boto3.client("secretsmanager")
    secret = json.loads(client.get_secret_value(SecretId=secret_arn)["SecretString"])
    return URL.create(
        "postgresql+psycopg",
        username=secret["username"],
        password=secret["password"],
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "5432")),
        database=os.environ.get("DB_NAME", "catalog"),
        query={"sslmode": "require"},
    )


def database_url() -> str | URL:
    if url := os.environ.get("DATABASE_URL"):
        return url
    return _url_from_secret()


@cache
def get_engine() -> Engine:
    # One small pool per Lambda container; pre-ping survives RDS restarts/idle drops.
    return create_engine(
        database_url(),
        pool_size=1,
        max_overflow=2,
        pool_pre_ping=True,
        pool_recycle=300,
    )


@cache
def session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)
