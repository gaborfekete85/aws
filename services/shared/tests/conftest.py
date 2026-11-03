import os

import pytest

os.environ.setdefault("AWS_DEFAULT_REGION", "eu-central-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("EVENT_BUS_NAME", "meeton-test")
os.environ.setdefault("EVENTS_BUS_NAME", "meeton-test")
os.environ.setdefault("AWS_LAMBDA_FUNCTION_NAME", "meeton-test")


@pytest.fixture
def bus():
    from moto import mock_aws

    with mock_aws():
        import boto3

        client = boto3.client("events")
        client.create_event_bus(Name="meeton-test")
        yield client
