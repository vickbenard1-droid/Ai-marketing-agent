"""
MetaCampaign model.

Distinct from app.models.campaign.Campaign (the internal, AI-generated
campaign concept from earlier weeks) - source_campaign_id links this
real Meta campaign back to that internal Campaign record when this
campaign was launched from an AI-generated plan, but a MetaCampaign can
also exist with no source_campaign_id at all. MetaCampaign is always
the SOURCE OF TRUTH for what actually exists and is spending on Meta;
Campaign is the internal planning/generation record.
"""
from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.campaign import Campaign
    from app.models.meta_ad_account import MetaAdAccount
    from app.models.organization import Organization


class MetaCampaignObjective(str, enum.Enum):
    OUTCOME_AWARENESS = "OUTCOME_AWARENESS"
    OUTCOME_TRAFFIC = "OUTCOME_TRAFFIC"
    OUTCOME_ENGAGEMENT = "OUTCOME_ENGAGEMENT"
    OUTCOME_LEADS = "OUTCOME_LEADS"
    OUTCOME_SALES = "OUTCOME_SALES"
    OUTCOME_APP_PROMOTION = "OUTCOME_APP_PROMOTION"


class MetaCampaignStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DELETED = "DELETED"
    ARCHIVED = "ARCHIVED"


class MetaCampaign(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "meta_campaigns"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    meta_ad_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meta_ad_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_campaign_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True
    )

    external_campaign_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    objective: Mapped[MetaCampaignObjective] = mapped_column(
        Enum(MetaCampaignObjective, name="meta_campaign_objective"), nullable=False
    )
    status: Mapped[MetaCampaignStatus] = mapped_column(
        Enum(MetaCampaignStatus, name="meta_campaign_status"), nullable=False, default=MetaCampaignStatus.PAUSED
    )
    daily_budget_cents: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    lifetime_budget_cents: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization")
    meta_ad_account: Mapped["MetaAdAccount"] = relationship("MetaAdAccount")
    source_campaign: Mapped[Optional["Campaign"]] = relationship("Campaign")

    def __repr__(self) -> str:
        return f"<MetaCampaign {self.name} status={self.status}>"
