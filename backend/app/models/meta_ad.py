"""MetaAd model - Meta's individual ad level (creative), child of MetaAdSet.

Status includes IN_REVIEW and REJECTED, distinct from the generic
ACTIVE/PAUSED lifecycle every other Meta object shares - an ad's own
creative goes through Meta's ad review process, a real state a
campaign/ad-set never enters.
"""
from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.meta_ad_set import MetaAdSet


class MetaAdStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DELETED = "DELETED"
    ARCHIVED = "ARCHIVED"
    IN_REVIEW = "IN_REVIEW"
    REJECTED = "REJECTED"


class MetaAd(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "meta_ads"

    meta_ad_set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meta_ad_sets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_ad_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[MetaAdStatus] = mapped_column(
        Enum(MetaAdStatus, name="meta_ad_status"), nullable=False, default=MetaAdStatus.PAUSED
    )
    headline: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    primary_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    call_to_action: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    meta_ad_set: Mapped["MetaAdSet"] = relationship("MetaAdSet")

    def __repr__(self) -> str:
        return f"<MetaAd {self.name} status={self.status}>"
