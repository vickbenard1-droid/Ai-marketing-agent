"""
CampaignAutonomySettings model.

One row per MetaCampaign, holding the Manual/Assisted/Autonomous mode
and the spec-required safety limits - one blanket mode per campaign
(not per action-type): a campaign is either fully Manual, fully
Assisted, or fully Autonomous, and every action the optimization agent
might propose for that campaign is governed by that single mode.

Every limit below is enforced fail-closed, same discipline as
app.meta_ads.spend_guard: a limit left unset blocks the corresponding
autonomous action rather than defaulting to unlimited.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.meta_campaign import MetaCampaign
    from app.models.user import User


class AutonomyLevel(str, enum.Enum):
    MANUAL = "manual"
    ASSISTED = "assisted"
    AUTONOMOUS = "autonomous"


class CampaignAutonomySettings(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "campaign_autonomy_settings"

    meta_campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meta_campaigns.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    autonomy_level: Mapped[AutonomyLevel] = mapped_column(
        Enum(AutonomyLevel, name="autonomy_level"), nullable=False, default=AutonomyLevel.MANUAL
    )
    max_daily_spend_cents: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    max_budget_increase_percent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_automated_actions_per_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    auto_executable_action_types: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    is_emergency_stopped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    emergency_stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    emergency_stopped_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    emergency_stop_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    meta_campaign: Mapped["MetaCampaign"] = relationship("MetaCampaign")
    emergency_stopped_by: Mapped[Optional["User"]] = relationship("User")

    def __repr__(self) -> str:
        return f"<CampaignAutonomySettings campaign={self.meta_campaign_id} level={self.autonomy_level}>"


class CampaignWhitelist(UUIDPKMixin, TimestampMixin, Base):
    """
    A separate, org-level table from CampaignAutonomySettings so the
    whitelist itself is independently auditable and the optimization
    agent's scan can query "which campaigns is it even allowed to
    consider" with one simple join. A campaign with autonomy settings
    but NO row here is never scanned - whitelisting is the "may the
    agent look at this at all" gate; autonomy settings is the "how much
    may it do" gate. Both must pass.
    """
    __tablename__ = "campaign_whitelists"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    meta_campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meta_campaigns.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    added_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    def __repr__(self) -> str:
        return f"<CampaignWhitelist campaign={self.meta_campaign_id}>"
