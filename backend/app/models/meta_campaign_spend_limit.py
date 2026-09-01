"""
MetaCampaignSpendLimit model.

Optional and additive to AdAccountSpendLimit, never a replacement for
it - a campaign may have a TIGHTER limit than its ad account's overall
cap, but every campaign still falls under the mandatory account-level
limit regardless of whether it has its own row here.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.meta_campaign import MetaCampaign


class MetaCampaignSpendLimit(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "meta_campaign_spend_limits"

    meta_campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta_campaigns.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    daily_spend_limit_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)

    meta_campaign: Mapped["MetaCampaign"] = relationship("MetaCampaign")

    def __repr__(self) -> str:
        return f"<MetaCampaignSpendLimit campaign={self.meta_campaign_id} limit={self.daily_spend_limit_cents}>"
