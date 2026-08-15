"""
Content asset service: upload, and (for images) real AI vision analysis.

Upload limits are hardcoded constants rather than config settings this
week - 10MB for images, 100MB for video, and a fixed allowed-type list.
These are reasonable defaults for a content-generation input (not a video
hosting platform), not values any deployment is expected to need to tune;
promoting them to settings.py is a trivial follow-up if that assumption
turns out wrong, not a design commitment made now.
"""
import base64
import uuid

from sqlalchemy.orm import Session

from app.ai_providers.base import (
    AIMessage,
    AIProviderError,
    AITaskType,
    ImageContentBlock,
)
from app.ai_providers.factory import get_ai_provider_for_task
from app.ai_usage.service import generate_and_track
from app.audit.service import write_audit_log
from app.models.ai_usage_log import AIUsageSource
from app.models.content_asset import AssetStatus, AssetType, ContentAsset
from app.storage.client import StorageError, build_object_key, delete_object, get_presigned_url, upload_bytes

MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_VIDEO_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB

ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
ALLOWED_VIDEO_CONTENT_TYPES = {"video/mp4", "video/quicktime", "video/webm"}

IMAGE_ANALYSIS_SYSTEM = (
    "You are looking at a product or marketing photo. Describe what's in the image "
    "in 2-4 sentences: the product/subject, setting, colors, and mood. Be concrete "
    "and factual - this description will be used to help write marketing content, "
    "so focus on details a copywriter would want to know. Do not invent brand names, "
    "prices, or claims that aren't visible in the image."
)


class AssetError(Exception):
    """Raised for asset failures the API layer should turn into 4xx responses."""


def upload_asset(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    filename: str,
    content_type: str,
    data: bytes,
) -> ContentAsset:
    if content_type in ALLOWED_IMAGE_CONTENT_TYPES:
        asset_type = AssetType.IMAGE
        size_limit = MAX_IMAGE_SIZE_BYTES
    elif content_type in ALLOWED_VIDEO_CONTENT_TYPES:
        asset_type = AssetType.VIDEO
        size_limit = MAX_VIDEO_SIZE_BYTES
    else:
        raise AssetError(
            f"Unsupported file type '{content_type}'. Allowed: "
            f"{sorted(ALLOWED_IMAGE_CONTENT_TYPES | ALLOWED_VIDEO_CONTENT_TYPES)}"
        )

    if len(data) > size_limit:
        raise AssetError(f"File exceeds the {size_limit // (1024 * 1024)}MB limit for this file type")
    if len(data) == 0:
        raise AssetError("File is empty")

    key = build_object_key(organization_id, filename)
    try:
        upload_bytes(key=key, data=data, content_type=content_type)
    except StorageError as exc:
        raise AssetError(f"Upload failed: {exc}") from exc

    asset = ContentAsset(
        organization_id=organization_id,
        uploaded_by_user_id=actor_user_id,
        asset_type=asset_type,
        status=AssetStatus.UPLOADED,
        original_filename=filename,
        storage_key=key,
        content_type=content_type,
        size_bytes=len(data),
    )
    db.add(asset)
    db.flush()

    write_audit_log(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="content_asset.uploaded",
        resource_type="ContentAsset",
        resource_id=str(asset.id),
        metadata={"asset_type": asset_type.value, "size_bytes": len(data)},
    )

    db.commit()
    db.refresh(asset)

    # Images get an immediate vision analysis pass - synchronous, not a
    # background task: the upload endpoint is already a single request
    # the user is waiting on, and a vision call is a single fast AI
    # request, not worth the complexity of a job queue + polling for this
    # week. Video is left at UPLOADED with no analysis attempt (see
    # ContentAsset's own docstring for why).
    if asset_type == AssetType.IMAGE:
        analyze_image(
            db, organization_id=organization_id, actor_user_id=actor_user_id, asset=asset, image_bytes=data
        )

    return asset


def analyze_image(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    asset: ContentAsset,
    image_bytes: bytes,
) -> ContentAsset:
    asset.status = AssetStatus.ANALYZING
    db.commit()

    provider = get_ai_provider_for_task(AITaskType.IMAGE_ANALYSIS)
    image_block = ImageContentBlock(
        data_base64=base64.b64encode(image_bytes).decode("ascii"), media_type=asset.content_type
    )

    try:
        result = generate_and_track(
            db,
            provider,
            [AIMessage(role="user", content=["Describe this image.", image_block])],
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            source=AIUsageSource.IMAGE_ANALYSIS,
            system=IMAGE_ANALYSIS_SYSTEM,
            max_tokens=300,
        )
    except AIProviderError as exc:
        asset.status = AssetStatus.FAILED
        asset.analysis_error = str(exc)
        db.commit()
        db.refresh(asset)
        return asset

    asset.ai_description = result.text
    asset.status = AssetStatus.ANALYZED
    db.commit()
    db.refresh(asset)
    return asset


def get_asset(db: Session, *, organization_id: uuid.UUID, asset_id: uuid.UUID) -> ContentAsset:
    asset = (
        db.query(ContentAsset)
        .filter(ContentAsset.id == asset_id, ContentAsset.organization_id == organization_id)
        .first()
    )
    if not asset:
        raise AssetError("Asset not found")
    return asset


def list_assets(db: Session, organization_id: uuid.UUID) -> list[ContentAsset]:
    return (
        db.query(ContentAsset)
        .filter(ContentAsset.organization_id == organization_id)
        .order_by(ContentAsset.created_at.desc())
        .all()
    )


def get_asset_url(asset: ContentAsset) -> str | None:
    """Returns a presigned read URL, or None if storage isn't configured
    (see app.storage.client.StorageNotConfiguredError) - callers show a
    'preview unavailable' state rather than erroring the whole request
    just because a signed URL couldn't be generated."""
    try:
        return get_presigned_url(asset.storage_key)
    except StorageError:
        return None


def delete_asset(db: Session, *, organization_id: uuid.UUID, asset_id: uuid.UUID) -> None:
    asset = get_asset(db, organization_id=organization_id, asset_id=asset_id)
    try:
        delete_object(asset.storage_key)
    except StorageError:
        # If the storage delete fails (e.g. storage briefly unavailable),
        # still remove the DB row - an orphaned S3 object is a cheap,
        # recoverable cost; a ContentAsset row that can never be deleted
        # because storage happened to be down is a worse outcome.
        pass
    db.delete(asset)
    db.commit()
