"""
Content asset endpoints.

Upload is gated on can_manage_content (uploading source material for
future content generation is a content-management action, not an
AI-execution one - the actual AI cost is the vision-analysis call inside
upload_asset(), which happens synchronously as part of upload; see
app/content/asset_service.py's own note on why that's not split into a
separate can_execute_ai_actions-gated step).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_org_member, require_permission
from app.content.asset_service import (
    AssetError,
    delete_asset,
    get_asset,
    get_asset_url,
    list_assets,
    upload_asset,
)
from app.db.session import get_db
from app.models.organization import OrganizationMember
from app.schemas.auth import MessageResponse
from app.schemas.content_asset import ContentAssetPublic, ContentAssetWithUrl

router = APIRouter(prefix="/content-assets", tags=["content-assets"])

# Read from the request body in chunks up to this size, then reject - a
# defense-in-depth cap independent of asset_service's own per-type limits
# (10MB image / 100MB video), so an oversized request body is rejected
# before its bytes are even fully read into memory.
MAX_UPLOAD_READ_BYTES = 100 * 1024 * 1024 + 1024  # 100MB (video ceiling) + a little headroom


def _to_public_with_url(asset) -> ContentAssetWithUrl:
    return ContentAssetWithUrl(
        **ContentAssetPublic.model_validate(asset).model_dump(),
        url=get_asset_url(asset),
    )


@router.post("", response_model=ContentAssetWithUrl, status_code=status.HTTP_201_CREATED)
async def upload_content_asset(
    file: UploadFile,
    member: OrganizationMember = Depends(require_permission("can_manage_content")),
    db: Session = Depends(get_db),
):
    data = await file.read(MAX_UPLOAD_READ_BYTES)
    if len(data) == MAX_UPLOAD_READ_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File is too large"
        )

    try:
        asset = upload_asset(
            db,
            organization_id=member.organization_id,
            actor_user_id=member.user_id,
            filename=file.filename or "upload",
            content_type=file.content_type or "application/octet-stream",
            data=data,
        )
    except AssetError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return _to_public_with_url(asset)


@router.get("", response_model=list[ContentAssetPublic])
def list_content_assets(
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    return list_assets(db, member.organization_id)


@router.get("/{asset_id}", response_model=ContentAssetWithUrl)
def get_content_asset(
    asset_id: uuid.UUID,
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    try:
        asset = get_asset(db, organization_id=member.organization_id, asset_id=asset_id)
    except AssetError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return _to_public_with_url(asset)


@router.delete("/{asset_id}", response_model=MessageResponse)
def delete_content_asset(
    asset_id: uuid.UUID,
    member: OrganizationMember = Depends(require_permission("can_manage_content")),
    db: Session = Depends(get_db),
):
    try:
        delete_asset(db, organization_id=member.organization_id, asset_id=asset_id)
    except AssetError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return MessageResponse(message="Asset deleted")
