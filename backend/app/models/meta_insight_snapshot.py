"""
MetaInsightSnapshot model.

One row per (entity, day) - entity_type/entity_id is polymorphic by
convention (a real, deliberate tradeoff already used elsewhere in this
app for join-target flexibility without a physical FK to 3 different
possible tables) since a snapshot can be at the campaign, ad set, or ad
level. Raw counts only, same "store raw, compute derived ratios fresh"
discipline used for every metrics table in this app - CTR/CPC/etc. are
computed on demand, never stored as columns that could drift from the
raw numbers underneath them.
"""
from __future__ import annotations

import enum
import uuid
from datetime import date as date_type
from typing import Optional

from sqlalchemy import BigInteger, Date, Enum, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin


class MetaInsightEntityType(str, enum.Enum):
    CAMPAIGN = "campaign"
    AD_SET = "ad_set"
    AD = "ad"


class MetaInsightSnapshot(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "meta_insight_snapshots"

    meta_ad_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    entity_type: Mapped[MetaInsightEntityType] = mapped_column(
        Enum(MetaInsightEntityType, name="meta_insight_entity_type"), nullable=False
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    date: Mapped[date_type] = mapped_column(Date, nullable=False)

    impressions: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    clicks: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    spend_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    reach: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    leads_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    purchases_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    revenue_cents: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)

    def __repr__(self) -> str:
        return f"<MetaInsightSnapshot {self.entity_type}={self.entity_id} date={self.date}>"
