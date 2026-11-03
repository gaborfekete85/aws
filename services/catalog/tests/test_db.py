import json

import boto3
from moto import mock_aws

from catalog import db


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
    assert url.query["sslmode"] == "verify-full"
    assert url.query["require_auth"] == "scram-sha-256"
    assert url.query["sslrootcert"] == str(db.RDS_CA_BUNDLE)


def test_rds_ca_bundle_ships_with_the_package() -> None:
    # build_lambda.sh copies the package directory, so the bundle lands in the zip.
    pem = db.RDS_CA_BUNDLE.read_text()
    assert pem.count("BEGIN CERTIFICATE") >= 100
    for region in ("eu-central-1", "eu-north-1"):
        assert f"Amazon RDS {region} Root CA RSA2048 G1" in _subjects(db.RDS_CA_BUNDLE)


def _subjects(bundle) -> str:
    from cryptography import x509

    certs = x509.load_pem_x509_certificates(bundle.read_bytes())
    return "\n".join(c.subject.rfc4514_string() for c in certs)


def test_sslmode_can_be_overridden(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_SSLMODE", "require")
    with mock_aws():
        arn = boto3.client("secretsmanager").create_secret(
            Name="meeton-dev-catalog-db",
            SecretString=json.dumps({"username": "meeton_dev", "password": "pw"}),
        )["ARN"]
        monkeypatch.setenv("DB_SECRET_ARN", arn)
        monkeypatch.setenv("DB_HOST", "db.example.com")
        url = db.database_url()
    assert not isinstance(url, str)
    assert url.query["sslmode"] == "require"


def test_database_url_env_wins(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/x")
    assert db.database_url() == "postgresql+psycopg://u:p@localhost/x"
