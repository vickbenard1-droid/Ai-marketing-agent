"""
ConversionType model.

Custom, business-defined conversion type names from the start - name is
free text (e.g. "Demo Booked", "Newsletter Signup"), NOT a fixed enum,
since every business measures success differently and this app has no
basis for predicting every possible conversion type a business might
care about.

category is a small, FIXED vocabulary used for generic cross-type
reasoning (e.g. "is this a lead-shaped conversion or a purchase-shaped
one" for rollups/dashboards that need to reason about a category of
conversions without knowing every business's specific naming) - NOT the
conversion type name itself.

counts_as_revenue distinguishes a conversion that should be summed into
revenue rollups (a purchase) from one that shouldn't (a lead, an
engagement) - explicit per-type rather than inferred from category,
since a business might reasonably want e.g. "Subscription Started" to
count as revenue even though SUBSCRIPTION is its own category, not
PURCHASE.
"""
from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.organization import Organization


class ConversionCategory(str, enum.Enum):
    LEAD = "lead"
    QUALIFICATION = "qualification"
    ENGAGEMENT = "engagement"
    PURCHASE = "purchase"
    SUBSCRIPTION = "subscription"
    OTHER = "other"


class ConversionType(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "conversion_types"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[ConversionCategory] = mapped_column(Enum(ConversionCategory, name="conversion_category"), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    counts_as_revenue: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self) -> str:
        return f"<ConversionType {self.name} category={self.category}>"
