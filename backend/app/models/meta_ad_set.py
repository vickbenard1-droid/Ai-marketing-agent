"""MetaAdSet model - Meta's ad-set level (targeting/budget/schedule), child of MetaCampaign."""
from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, BigInteger, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.meta_campaign import MetaCampaign


class MetaAdSetStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DELETED = "DELETED"
    ARCHIVED = "ARCHIVED"


class MetaAdSet(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "meta_ad_sets"

    meta_campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meta_campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_ad_set_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[MetaAdSetStatus] = mapped_column(
        Enum(MetaAdSetStatus, name="meta_ad_set_status"), nullable=False, default=MetaAdSetStatus.PAUSED
    )
    daily_budget_cents: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    targeting_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    meta_campaign: Mapped["MetaCampaign"] = relationship("MetaCampaign")

    def __repr__(self) -> str:
        return f"<MetaAdSet {self.name} status={self.status}>"
