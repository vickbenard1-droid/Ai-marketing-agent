"""
Content endpoints (CRUD half - see content_generation.py for generation
itself, gated on a different permission).

Reading (list/get) requires only org membership. Editing/approving/
deleting is gated on can_manage_content - the permission flag seeded in
Week 2 specifically anticipating this feature (Owner/Admin/Manager/
Content Manager have it, Analyst/Viewer don't).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_org_member, require_permission
from app.content.service import (
    ContentError,
    approve_content,
    delete_content,
    get_content,
    get_repurpose_batch,
    list_content,
    update_content,
)
from app.db.session import get_db
from app.models.content import ContentStatus, ContentType
from app.models.organization import OrganizationMember
from app.schemas.auth import MessageResponse
from app.schemas.content import ContentPublic, ContentUpdate, RepurposeBatchPublic

router = APIRouter(prefix="/content", tags=["content"])


@router.get("", response_model=list[ContentPublic])
def list_my_content(
    status_filter: ContentStatus | None = Query(default=None, alias="status"),
    content_type: ContentType | None = Query(default=None),
    search: str | None = Query(default=None, max_length=255),
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    """Backs the Content Studio library - status filter (draft/approved),
    content type filter, and free-text search, all optional and
    combinable."""
    return list_content(
        db, member.organization_id, status=status_filter, content_type=content_type, search=search
    )


@router.get("/repurpose-batches/{batch_id}", response_model=RepurposeBatchPublic)
def get_repurpose_batch_detail(
    batch_id: uuid.UUID,
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    try:
        return get_repurpose_batch(db, organization_id=member.organization_id, batch_id=batch_id)
    except ContentError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{content_id}", response_model=ContentPublic)
def get_content_detail(
    content_id: uuid.UUID,
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    try:
        return get_content(db, organization_id=member.organization_id, content_id=content_id)
    except ContentError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{content_id}", response_model=ContentPublic)
def update_content_item(
    content_id: uuid.UUID,
    payload: ContentUpdate,
    member: OrganizationMember = Depends(require_permission("can_manage_content")),
    db: Session = Depends(get_db),
):
    try:
        return update_content(
            db,
            organization_id=member.organization_id,
            content_id=content_id,
            updates=payload.model_dump(exclude_unset=True),
        )
    except ContentError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{content_id}/approve", response_model=ContentPublic)
def approve_content_item(
    content_id: uuid.UUID,
    member: OrganizationMember = Depends(require_permission("can_manage_content")),
    db: Session = Depends(get_db),
):
    try:
        return approve_content(
            db, organization_id=member.organization_id, actor_user_id=member.user_id, content_id=content_id
        )
    except ContentError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{content_id}", response_model=MessageResponse)
def delete_content_item(
    content_id: uuid.UUID,
    member: OrganizationMember = Depends(require_permission("can_manage_content")),
    db: Session = Depends(get_db),
):
    try:
        delete_content(db, organization_id=member.organization_id, content_id=content_id)
    except ContentError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return MessageResponse(message="Content deleted")
