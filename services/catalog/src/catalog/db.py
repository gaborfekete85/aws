"""Database engine for the Catalog (PostgreSQL + PostGIS on RDS).

Connection settings come from, in order:
1. ``DATABASE_URL`` (local dev, CI, tests), or
2. ``DB_HOST`` / ``DB_NAME`` / ``DB_SECRET_ARN`` (Lambda): the Secrets Manager
   secret (RDS-managed, or the dev login on a shared instance, #39) holds
   ``username`` and ``password``.

Lambda connections verify the server: TLS ``verify-full`` against the bundled
Amazon RDS CA bundle (every RDS region and CA generation), so a spoofed host
cannot collect the password, and ``require_auth=scram-sha-256`` so the password
never travels in a form the server could downgrade to. This matters once the
database is reached over the internet (dev on a shared instance), and costs
nothing inside a VPC. ``DB_SSLMODE`` overrides the mode (e.g. for a non-RDS host).
"""

from __future__ import annotations

import json
import os
from functools import cache
from pathlib import Path
from typing import Any

import boto3
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

# https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem
RDS_CA_BUNDLE = Path(__file__).with_name("rds-ca-bundle.pem")


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
        query={
            "sslmode": os.environ.get("DB_SSLMODE", "verify-full"),
            "sslrootcert": str(RDS_CA_BUNDLE),
            "require_auth": "scram-sha-256",
        },
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
