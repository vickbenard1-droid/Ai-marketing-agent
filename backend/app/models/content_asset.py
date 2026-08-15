"""
ContentAsset model.

Represents an uploaded file (image or video) that content generation can
draw on. Organization-scoped, S3-backed (see app/storage/client.py — the
`storage_key` column is the S3 object key, never a public URL; presigned
URLs are generated on read, not stored, so they can't go stale in the DB).

ai_description is populated by a real vision-model call for images (see
app/content/asset_service.py::analyze_image) — for video, no vision
analysis is performed (see AssetType.VIDEO's own note below), so
ai_description stays null and content generation relies on whatever text
description the user provides alongside the video reference.

status tracks the upload pipeline: UPLOADED (file stored, not yet
analyzed) -> ANALYZING -> ANALYZED (image description ready) | FAILED (the
vision call errored — the asset itself is still usable, just without an
AI description; see asset_service.py for how this is surfaced).
"""
from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class AssetType(str, enum.Enum):
    IMAGE = "image"
    # Video files are stored and can be referenced by content generation
    # (the user can describe what's in the video), but no video-vision
    # analysis is performed this week — that's a materially different
    # (and more expensive) capability than single-image vision calls, and
    # isn't required to satisfy the spec's "provide videos" input option,
    # which is satisfied by upload + storage + a user-supplied
    # description.
    VIDEO = "video"


class AssetStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    FAILED = "failed"


class ContentAsset(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "content_assets"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uploaded_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    asset_type: Mapped[AssetType] = mapped_column(Enum(AssetType, name="asset_type"), nullable=False)
    status: Mapped[AssetStatus] = mapped_column(
        Enum(AssetStatus, name="asset_status"), nullable=False, default=AssetStatus.UPLOADED
    )

    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Populated by a real vision-model call for images — see module
    # docstring. User-editable after generation, same "AI drafts, human
    # can correct" pattern as AdCopyVariant.is_edited, though we don't
    # track an edited flag here since there's only one field to edit.
    ai_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    analysis_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization")
    uploaded_by: Mapped[Optional["User"]] = relationship("User")

    def __repr__(self) -> str:
        return f"<ContentAsset {self.asset_type} {self.status} org={self.organization_id}>"
