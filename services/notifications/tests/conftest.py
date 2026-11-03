from __future__ import annotations

import os
import uuid

import pytest

os.environ.setdefault("AWS_DEFAULT_REGION", "eu-central-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("EVENT_BUS_NAME", "meeton-test")
os.environ.setdefault("SENDER_EMAIL", "no-reply@meeton.test")


@pytest.fixture
def aws(monkeypatch):
    """moto SES (sender verified) + the sent-marker table."""
    from moto import mock_aws

    from notifications import sender

    name = f"notifications-{uuid.uuid4().hex[:8]}"
    monkeypatch.setenv("NOTIFICATIONS_TABLE", name)
    monkeypatch.delenv("DYNAMODB_ENDPOINT_URL", raising=False)
    sender.ses.cache_clear()
    sender.dynamodb.cache_clear()
    with mock_aws():
        import boto3

        boto3.client("ses").verify_email_identity(EmailAddress=os.environ["SENDER_EMAIL"])
        sender.dynamodb().create_table(**sender.table_definition(name))
        yield
    sender.ses.cache_clear()
    sender.dynamodb.cache_clear()


def sent_emails():
    """Everything moto's SES backend accepted."""
    from moto.core import DEFAULT_ACCOUNT_ID
    from moto.ses.models import ses_backends

    return ses_backends[DEFAULT_ACCOUNT_ID]["eu-central-1"].sent_messages


@pytest.fixture
def outbox():
    return sent_emails


def sqs_record(detail_type: str, detail: dict, message_id: str | None = None) -> dict:
    import json

    from meeton_shared.testing import eventbridge_event

    return {
        "messageId": message_id or str(uuid.uuid4()),
        "receiptHandle": "rh",
        "body": json.dumps(eventbridge_event(detail, detail_type)),
        "attributes": {"ApproximateReceiveCount": "1"},
        "eventSource": "aws:sqs",
    }
