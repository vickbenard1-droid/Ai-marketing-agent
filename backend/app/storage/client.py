"""
S3-compatible storage client.

Wraps boto3's S3 client with the app's own error type (StorageError) so
callers never need to catch botocore exceptions directly — same pattern
as app.ai_providers wrapping httpx/provider errors. Config
(S3_ENDPOINT_URL/S3_ACCESS_KEY_ID/etc.) has existed since Week 1 but was
never wired to any code until this module.

S3_ENDPOINT_URL is deliberately supported (not just real AWS S3) so this
works against any S3-compatible provider (MinIO for local dev, R2,
DigitalOcean Spaces, etc.) without code changes — only .env changes.

Objects are stored under a content-addressed-ish key
(organizations/{org_id}/content-assets/{uuid}.{ext}) so two orgs' assets
never collide and a listing by org is a simple prefix query if ever
needed, without requiring a DB join for basic isolation.
"""
import uuid
from datetime import timedelta

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings


class StorageError(Exception):
    """Raised for any storage failure — callers never need to catch
    botocore exceptions directly."""


class StorageNotConfiguredError(StorageError):
    """Raised when S3 credentials/bucket aren't set. Distinct from other
    StorageErrors so callers (e.g. the upload endpoint) can return a
    clear 'file uploads aren't configured on this deployment' message
    rather than a generic failure."""


def _get_client():
    if not settings.S3_ACCESS_KEY_ID or not settings.S3_SECRET_ACCESS_KEY or not settings.S3_BUCKET_NAME:
        raise StorageNotConfiguredError(
            "S3 storage is not configured (S3_ACCESS_KEY_ID / S3_SECRET_ACCESS_KEY / S3_BUCKET_NAME)"
        )
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL or None,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        region_name=settings.S3_REGION,
        config=BotoConfig(signature_version="s3v4"),
    )


def build_object_key(organization_id: uuid.UUID, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    # Strip anything that isn't alphanumeric from the extension — a
    # filename like "photo.jpg?x=1" (a malformed but plausible client
    # upload) shouldn't produce a key with a query string baked into it.
    ext = "".join(c for c in ext if c.isalnum()) or "bin"
    return f"organizations/{organization_id}/content-assets/{uuid.uuid4()}.{ext}"


def upload_bytes(*, key: str, data: bytes, content_type: str) -> None:
    try:
        client = _get_client()
        client.put_object(Bucket=settings.S3_BUCKET_NAME, Key=key, Body=data, ContentType=content_type)
    except StorageNotConfiguredError:
        raise
    except (BotoCoreError, ClientError) as exc:
        raise StorageError(f"Failed to upload object: {exc}") from exc


def get_presigned_url(key: str, *, expires_in: timedelta = timedelta(hours=1)) -> str:
    """
    Returns a temporary signed URL for reading a private object — used so
    the frontend can display/download an uploaded asset without the
    bucket needing to be public and without proxying bytes through the
    API server on every view.
    """
    try:
        client = _get_client()
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET_NAME, "Key": key},
            ExpiresIn=int(expires_in.total_seconds()),
        )
    except StorageNotConfiguredError:
        raise
    except (BotoCoreError, ClientError) as exc:
        raise StorageError(f"Failed to generate presigned URL: {exc}") from exc


def delete_object(key: str) -> None:
    try:
        client = _get_client()
        client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key)
    except StorageNotConfiguredError:
        raise
    except (BotoCoreError, ClientError) as exc:
        raise StorageError(f"Failed to delete object: {exc}") from exc
