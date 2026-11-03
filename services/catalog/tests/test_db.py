import json

import boto3
from catalog import db
from moto import mock_aws


def test_url_built_from_rds_managed_secret(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with mock_aws():
        arn = boto3.client("secretsmanager").create_secret(
            Name="rds!db-test",
            SecretString=json.dumps({"username": "catalog_admin", "password": "s3cr3t"}),
        )["ARN"]
        monkeypatch.setenv("DB_SECRET_ARN", arn)
        monkeypatch.setenv("DB_HOST", "db.internal")
        monkeypatch.setenv("DB_NAME", "catalog")
        url = db.database_url()
    assert not isinstance(url, str)
    assert url.username == "catalog_admin"
    assert url.password == "s3cr3t"
    assert url.host == "db.internal"
    assert url.query["sslmode"] == "require"


def test_database_url_env_wins(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/x")
    assert db.database_url() == "postgresql+psycopg://u:p@localhost/x"
