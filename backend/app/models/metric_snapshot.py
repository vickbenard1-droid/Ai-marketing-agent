"""
MetricSnapshot model.

Source-agnostic (unlike Week 7's MetaInsightSnapshot, which is
Meta-specific) - one row per (organization, source, entity_type,
entity_id, date), storing ONLY raw counts. Derived ratios (CTR, CPC,
CPM, cost-per-lead, CPA, ROAS, conversion rate) are computed fresh from
these raw numbers in app/analytics/metrics.py, never stored as columns
here - this is the same "raw counts only, compute derived values on
demand" discipline already established for Week 7's MetaInsightSnapshot,
applied at the cross-platform level this table exists for.

MetaInsightSnapshot itself is NOT replaced by this table - it stays the
Meta-specific detail table Week 7's own sync/insights endpoints read
from directly; app/analytics/sync_orchestrator.py is the one place that
translates a MetaInsightSnapshot row into a MetricSnapshot row, at a
clearly defined boundary, rather than this table silently duplicating
or replacing Week 7's existing storage.

entity_type/entity_id is polymorphic by convention (same tradeoff
already accepted for MetaInsightSnapshot and other tables in this app) -
a snapshot can be at the organization level (no specific entity, e.g. a
Shopify store's daily totals), campaign level, ad level, or page level
(for website analytics).
"""
from __future__ import annotations

import enum
import uuid
from datetime import date as date_type
from typing import Optional

from sqlalchemy import BigInteger, Date, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin
from app.models.connected_account import PlatformType


class MetricEntityType(str, enum.Enum):
    ORGANIZATION = "organization"
    CAMPAIGN = "campaign"
    AD = "ad"
    PAGE = "page"


class MetricSnapshot(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "metric_snapshots"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[PlatformType] = mapped_column(Enum(PlatformType, name="platform_type"), nullable=False)
    entity_type: Mapped[MetricEntityType] = mapped_column(Enum(MetricEntityType, name="metric_entity_type"), nullable=False)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    date: Mapped[date_type] = mapped_column(Date, nullable=False)

    impressions: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    clicks: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    spend_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    leads_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    purchases_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    revenue_cents: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    reach: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")

    def __repr__(self) -> str:
        return f"<MetricSnapshot source={self.source} {self.entity_type}={self.entity_id} date={self.date}>"
