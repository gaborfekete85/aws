"""Cover picture presigned uploads (unit) and the upload/attach API (integration)."""

import uuid
from urllib.parse import parse_qs, urlparse

import boto3
import pytest
from catalog.media import MAX_BYTES, CoverPictures
from localbini_shared.errors import ValidationError
from moto import mock_aws

from .conftest import ORGANIZER, OTHER_ORGANIZER


@pytest.fixture
def covers():
    with mock_aws():
        s3 = boto3.client("s3", region_name="eu-central-1")
        s3.create_bucket(
            Bucket="media", CreateBucketConfiguration={"LocationConstraint": "eu-central-1"}
        )
        yield CoverPictures("media", "cdn.example.net", client=s3), s3


def test_presigned_put_signs_type_and_exact_length(covers) -> None:
    pictures, _ = covers
    event_id = uuid.uuid4()
    ticket = pictures.new_upload(event_id, "image/jpeg", 123_456)

    query = parse_qs(urlparse(ticket.upload_url).query)
    signed = query["X-Amz-SignedHeaders"][0].split(";")
    assert {"content-length", "content-type", "host"} <= set(signed)
    assert query["X-Amz-Expires"] == ["300"]
    assert ticket.key.startswith(f"covers/{event_id}/") and ticket.key.endswith(".jpg")
    assert ticket.headers == {"Content-Type": "image/jpeg", "Content-Length": "123456"}


@pytest.mark.parametrize("content_type", ["image/gif", "application/pdf", "text/html", ""])
def test_only_image_types(covers, content_type) -> None:
    with pytest.raises(ValidationError, match="JPEG, PNG or WebP"):
        covers[0].new_upload(uuid.uuid4(), content_type, 100)


@pytest.mark.parametrize("size", [0, MAX_BYTES + 1])
def test_size_limit(covers, size) -> None:
    with pytest.raises(ValidationError, match="5 MB"):
        covers[0].new_upload(uuid.uuid4(), "image/png", size)


def test_verify_uploaded(covers) -> None:
    pictures, s3 = covers
    with pytest.raises(ValidationError, match="not been uploaded"):
        pictures.verify_uploaded("covers/x/missing.jpg")
    s3.put_object(Bucket="media", Key="covers/x/a.png", Body=b"\x89PNG", ContentType="image/png")
    pictures.verify_uploaded("covers/x/a.png")
    s3.put_object(Bucket="media", Key="covers/x/b.svg", Body=b"<svg/>", ContentType="image/svg+xml")
    with pytest.raises(ValidationError, match="not an allowed image"):
        pictures.verify_uploaded("covers/x/b.svg")


def test_url_for_uses_cloudfront() -> None:
    pictures = CoverPictures("media", "d111.cloudfront.net", client=object())
    assert pictures.url_for("covers/e/1.jpg") == "https://d111.cloudfront.net/covers/e/1.jpg"
    assert pictures.url_for(None) is None


@pytest.mark.integration
def test_upload_then_attach_returns_cloudfront_url(call, event_body, media) -> None:
    _, event = call("POST", "/events", claims=ORGANIZER, body=event_body())
    path = {"event_id": event["id"]}

    status, ticket = call(
        "POST",
        "/events/{event_id}/cover-picture/upload-url",
        claims=ORGANIZER,
        path=path,
        body={"content_type": "image/webp", "content_length": 2048},
    )
    assert status == 201
    assert ticket["method"] == "PUT"

    # the browser PUTs the file; simulate it
    media.put_object(
        Bucket="localbini-test-media", Key=ticket["key"], Body=b"x" * 2048, ContentType="image/webp"
    )
    status, body = call(
        "PUT",
        "/events/{event_id}/cover-picture",
        claims=ORGANIZER,
        path=path,
        body={"key": ticket["key"]},
    )
    assert status == 200
    assert body["cover_picture_key"] == ticket["key"]
    assert body["cover_picture_url"] == f"https://cdn.example.net/{ticket['key']}"


@pytest.mark.integration
def test_cannot_attach_a_key_from_another_event(call, event_body, media) -> None:
    _, mine = call("POST", "/events", claims=ORGANIZER, body=event_body())
    _, other = call("POST", "/events", claims=ORGANIZER, body=event_body(title="Other"))
    foreign_key = f"covers/{other['id']}/x.jpg"
    media.put_object(
        Bucket="localbini-test-media", Key=foreign_key, Body=b"x", ContentType="image/jpeg"
    )
    status, _ = call(
        "PUT",
        "/events/{event_id}/cover-picture",
        claims=ORGANIZER,
        path={"event_id": mine["id"]},
        body={"key": foreign_key},
    )
    assert status == 422


@pytest.mark.integration
def test_other_organizer_cannot_get_an_upload_url(call, event_body, media) -> None:
    _, event = call("POST", "/events", claims=ORGANIZER, body=event_body())
    status, _ = call(
        "POST",
        "/events/{event_id}/cover-picture/upload-url",
        claims=OTHER_ORGANIZER,
        path={"event_id": event["id"]},
        body={"content_type": "image/png", "content_length": 10},
    )
    assert status == 403


@pytest.mark.integration
def test_attach_before_upload_is_422(call, event_body, media) -> None:
    _, event = call("POST", "/events", claims=ORGANIZER, body=event_body())
    status, body = call(
        "PUT",
        "/events/{event_id}/cover-picture",
        claims=ORGANIZER,
        path={"event_id": event["id"]},
        body={"key": f"covers/{event['id']}/never.jpg"},
    )
    assert status == 422
    assert "not been uploaded" in body["message"]
