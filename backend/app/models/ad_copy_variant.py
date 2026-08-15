"""
AdCopyVariant model.

One row per ad copy variant (not a JSON array on Campaign) — deliberately,
for two reasons the JSON-blob sections above don't need to satisfy:

1. Individually editable: the campaign builder review step (wizard step 7)
   lets a person edit one variant's headline without touching the others.
   A row per variant makes that a normal single-row UPDATE; a JSON array
   would need read-modify-write of the whole blob for a one-field edit.
2. Referenced by experiments: app/models/experiment.py's A/B test model
   points at specific variant ids to say "this experiment is testing
   headline A vs headline B" — that reference only makes sense if variants
   are addressable rows, not items in an untyped array.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.campaign import Campaign


class AdCopyVariant(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "ad_copy_variants"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # 1-indexed display order (variant 1, 2, 3...) — the order the AI
    # generated them in, preserved for a stable, predictable UI list.
    variant_number: Mapped[int] = mapped_column(nullable=False)

    headline: Mapped[str] = mapped_column(String(255), nullable=False)
    primary_text: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    call_to_action: Mapped[str] = mapped_column(String(100), nullable=False)

    # Whether a human has edited this variant since it was generated —
    # lets the review UI show "edited" vs "as generated" without a
    # separate audit trail for something this lightweight.
    is_edited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="ad_copy_variants")

    def __repr__(self) -> str:
        return f"<AdCopyVariant #{self.variant_number} campaign={self.campaign_id}>"
