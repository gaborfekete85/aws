"""Cover picture uploads: short-lived presigned S3 PUTs, served through CloudFront.

The presigned PUT signs both ``Content-Type`` and the exact ``Content-Length`` the
client declared, so S3 rejects any upload whose type or size differs. That is
how a PUT URL enforces "images only, at most 5 MB".
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Any

import boto3
from botocore.exceptions import ClientError

from localbini_shared.errors import ValidationError

ALLOWED_CONTENT_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
MAX_BYTES = 5 * 1024 * 1024
URL_TTL_SECONDS = 300


@dataclass(frozen=True)
class UploadTicket:
    key: str
    upload_url: str
    headers: dict[str, str]
    expires_in: int
    max_bytes: int


class CoverPictures:
    def __init__(
        self, bucket: str | None = None, cdn_domain: str | None = None, client: Any = None
    ) -> None:
        self.bucket = bucket or os.environ.get("MEDIA_BUCKET", "")
        self.cdn_domain = (
            cdn_domain if cdn_domain is not None else os.environ.get("MEDIA_CDN_DOMAIN")
        )
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = boto3.client("s3")
        return self._client

    def url_for(self, key: str | None) -> str | None:
        if not key or not self.cdn_domain:
            return None
        return f"https://{self.cdn_domain}/{key}"

    def new_upload(
        self, event_id: uuid.UUID, content_type: str, content_length: int
    ) -> UploadTicket:
        ext = ALLOWED_CONTENT_TYPES.get(content_type)
        if ext is None:
            raise ValidationError(
                "Cover picture must be a JPEG, PNG or WebP image",
                details={"field": "content_type", "allowed": sorted(ALLOWED_CONTENT_TYPES)},
            )
        if not 0 < content_length <= MAX_BYTES:
            raise ValidationError(
                "Cover picture must be at most 5 MB",
                details={"field": "content_length", "max_bytes": MAX_BYTES},
            )
        key = f"covers/{event_id}/{uuid.uuid4()}.{ext}"
        url = self.client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ContentType": content_type,
                "ContentLength": content_length,
            },
            ExpiresIn=URL_TTL_SECONDS,
            HttpMethod="PUT",
        )
        return UploadTicket(
            key=key,
            upload_url=url,
            headers={"Content-Type": content_type, "Content-Length": str(content_length)},
            expires_in=URL_TTL_SECONDS,
            max_bytes=MAX_BYTES,
        )

    def verify_uploaded(self, key: str) -> None:
        """The object must exist, be an allowed image type and within the size limit."""
        try:
            head = self.client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as error:
            raise ValidationError(
                "The Cover picture has not been uploaded yet", details={"field": "key"}
            ) from error
        if head.get("ContentType") not in ALLOWED_CONTENT_TYPES:
            raise ValidationError("Uploaded file is not an allowed image", details={"field": "key"})
        if int(head.get("ContentLength", 0)) > MAX_BYTES:
            raise ValidationError("Uploaded file is too large", details={"field": "key"})
