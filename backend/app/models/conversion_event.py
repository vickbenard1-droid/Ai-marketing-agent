"""
ConversionEvent model.

touchpoints_json stores ORDERED touchpoint history (a list of dicts,
each with at minimum source/entity_type/entity_id/touched_at) - real
first/last/campaign-level attribution is COMPUTED from this history on
demand (see app/analytics/attribution.py), never stored as a pre-picked
"the" attributed touchpoint. Storing a single pre-computed
attribution_source column would silently privilege one attribution
model over every other; keeping the raw touchpoint sequence lets any
model be computed from the same underlying data, and lets a person see
exactly which touchpoints existed even if they disagree with a
particular model's conclusion.

converted_entity_type / converted_entity_id identify what business
record this conversion corresponds to, if any - deliberately
loosely-typed (polymorphic by convention) rather than a hard FK to one
specific table, since a conversion could plausibly correspond to a CRM
contact, a Shopify order, or nothing with its own row at all (e.g. a
simple newsletter signup). This is intentionally left open for a later
week to give one specific category (e.g. "lead") a real first-class
entity to point at, without needing a schema migration to change the
FK target.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, BigInteger, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin
from app.models.connected_account import PlatformType

if TYPE_CHECKING:
    from app.models.conversion_type import ConversionType
    from app.models.organization import Organization


class ConversionEvent(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "conversion_events"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversion_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversion_types.id", ondelete="CASCADE"), nullable=False, index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value_cents: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    reported_by_source: Mapped[PlatformType] = mapped_column(Enum(PlatformType, name="platform_type"), nullable=False)

    converted_entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    converted_entity_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    touchpoints_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    organization: Mapped["Organization"] = relationship("Organization")
    conversion_type: Mapped["ConversionType"] = relationship("ConversionType")

    def __repr__(self) -> str:
        return f"<ConversionEvent type={self.conversion_type_id} occurred_at={self.occurred_at}>"
