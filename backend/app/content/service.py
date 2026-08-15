"""
Content CRUD service - the non-generation half of content management
(see app/content/generation_service.py and repurpose_service.py for
generation itself). Same organization-scoped, status-gated-editing
pattern as app.campaigns.service.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.audit.service import write_audit_log
from app.models.content import Content, ContentStatus, ContentType
from app.models.content_repurpose_batch import ContentRepurposeBatch


class ContentError(Exception):
    """Raised for content failures the API layer should turn into 4xx responses."""


def list_content(
    db: Session,
    organization_id: uuid.UUID,
    *,
    status: ContentStatus | None = None,
    content_type: ContentType | None = None,
    search: str | None = None,
) -> list[Content]:
    """
    Backs the Content Studio library's search/filter UI. `search` does a
    simple case-insensitive substring match against title and body - this
    app has no full-text search index, and a plain LIKE query is
    sufficient for a per-organization content library that isn't expected
    to grow into the tens of thousands of rows any time soon; revisit with
    a real search backend if that assumption stops holding.
    """
    query = db.query(Content).filter(Content.organization_id == organization_id)
    if status:
        query = query.filter(Content.status == status)
    if content_type:
        query = query.filter(Content.content_type == content_type)
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Content.title.ilike(like), Content.body.ilike(like)))
    return query.order_by(Content.created_at.desc()).all()


def get_content(db: Session, *, organization_id: uuid.UUID, content_id: uuid.UUID) -> Content:
    content = (
        db.query(Content)
        .filter(Content.id == content_id, Content.organization_id == organization_id)
        .first()
    )
    if not content:
        raise ContentError("Content not found")
    return content


def update_content(
    db: Session, *, organization_id: uuid.UUID, content_id: uuid.UUID, updates: dict
) -> Content:
    content = get_content(db, organization_id=organization_id, content_id=content_id)
    if content.status == ContentStatus.APPROVED:
        raise ContentError("This content has already been approved and can no longer be edited")

    for field, value in updates.items():
        setattr(content, field, value)

    db.commit()
    db.refresh(content)
    return content


def approve_content(
    db: Session, *, organization_id: uuid.UUID, actor_user_id: uuid.UUID | None, content_id: uuid.UUID
) -> Content:
    content = get_content(db, organization_id=organization_id, content_id=content_id)
    content.status = ContentStatus.APPROVED
    content.approved_at = datetime.now(timezone.utc)
    content.approved_by_user_id = actor_user_id

    write_audit_log(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="content.approved",
        resource_type="Content",
        resource_id=str(content.id),
    )

    db.commit()
    db.refresh(content)
    return content


def delete_content(db: Session, *, organization_id: uuid.UUID, content_id: uuid.UUID) -> None:
    content = get_content(db, organization_id=organization_id, content_id=content_id)
    db.delete(content)
    db.commit()


def get_repurpose_batch(
    db: Session, *, organization_id: uuid.UUID, batch_id: uuid.UUID
) -> ContentRepurposeBatch:
    batch = (
        db.query(ContentRepurposeBatch)
        .filter(
            ContentRepurposeBatch.id == batch_id, ContentRepurposeBatch.organization_id == organization_id
        )
        .first()
    )
    if not batch:
        raise ContentError("Repurpose batch not found")
    return batch
