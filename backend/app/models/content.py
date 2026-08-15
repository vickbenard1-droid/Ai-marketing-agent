"""
Content model.

One row per generated piece of content - a Facebook post, a blog article,
a product description, etc. (see ContentType for the full spec list).
Organization-scoped, matching every other tenant-scoped table.

Source tracking (source_text, source_url, source_asset_id) records what
the content was generated from, per the spec's list of input types
(text, product info, images, videos, URLs, product descriptions) - kept
as separate nullable fields rather than one polymorphic "source" blob,
since a single generation can combine more than one source (e.g. a
product description plus a photo), and each has a genuinely different
shape (a URL is a string, an asset is a foreign key).

status: DRAFT (generated, editable, not yet reviewed) -> APPROVED (a
human has signed off on it as ready to use). There is no PUBLISHED status
- the spec explicitly excludes automatic publishing this week; approval
here means "ready," not "live," matching the same distinction Campaign's
own docstring draws for campaign approval vs. launch.

brand_voice_used reuses the same Postgres enum type as
BusinessProfile.brand_voice (same name="brand_voice" - SQLAlchemy treats
two Enum columns with the same name as sharing one Postgres type rather
than creating a second one) since it's the identical concept, just
recorded per-content-item instead of as the org's current default.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin
from app.models.business_profile import BrandVoice

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User
    from app.models.content_asset import ContentAsset
    from app.models.content_repurpose_batch import ContentRepurposeBatch
    from app.models.seo_content import SEOContent


class ContentType(str, enum.Enum):
    FACEBOOK_POST = "facebook_post"
    INSTAGRAM_CAPTION = "instagram_caption"
    LINKEDIN_POST = "linkedin_post"
    X_POST = "x_post"
    TIKTOK_CAPTION = "tiktok_caption"
    YOUTUBE_TITLE = "youtube_title"
    YOUTUBE_DESCRIPTION = "youtube_description"
    BLOG_POST = "blog_post"
    PRODUCT_DESCRIPTION = "product_description"
    EMAIL = "email"
    VIDEO_SCRIPT = "video_script"
    HOOK = "hook"


class ContentStatus(str, enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"


class Content(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "content_items"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    content_type: Mapped[ContentType] = mapped_column(Enum(ContentType, name="content_type"), nullable=False)
    status: Mapped[ContentStatus] = mapped_column(
        Enum(ContentStatus, name="content_status"), nullable=False, default=ContentStatus.DRAFT
    )

    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    source_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    source_asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_assets.id", ondelete="SET NULL"), nullable=True
    )

    brand_voice_used: Mapped[Optional[BrandVoice]] = mapped_column(
        Enum(BrandVoice, name="brand_voice"), nullable=True
    )

    repurpose_batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_repurpose_batches.id", ondelete="SET NULL"), nullable=True
    )

    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    organization: Mapped["Organization"] = relationship("Organization")
    created_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by_user_id])
    approved_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[approved_by_user_id])
    source_asset: Mapped[Optional["ContentAsset"]] = relationship("ContentAsset")
    repurpose_batch: Mapped[Optional["ContentRepurposeBatch"]] = relationship(
        "ContentRepurposeBatch", back_populates="items"
    )
    seo: Mapped[Optional["SEOContent"]] = relationship(
        "SEOContent", back_populates="content", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Content {self.content_type} ({self.status}) org={self.organization_id}>"
