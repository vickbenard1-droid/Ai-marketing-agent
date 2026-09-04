"""
AutomatedActionLog model.

The real counter behind max_automated_actions_per_day - a campaign's
autonomous actions today are counted by querying real rows here, never
trusted from an in-memory counter. Deliberately append-only and
separate from OptimizationDecision.status (rather than counting
status=EXECUTED rows) so a later status correction can never
retroactively change what already counted toward a day's rate limit.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.meta_campaign import MetaCampaign
    from app.models.optimization_decision import OptimizationDecision
    from app.models.organization import Organization


class AutomatedActionLog(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "automated_action_logs"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    meta_campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meta_campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    optimization_decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("optimization_decisions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    executed_via: Mapped[str] = mapped_column(String(20), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    organization: Mapped["Organization"] = relationship("Organization")
    meta_campaign: Mapped["MetaCampaign"] = relationship("MetaCampaign")
    optimization_decision: Mapped["OptimizationDecision"] = relationship("OptimizationDecision")

    def __repr__(self) -> str:
        return f"<AutomatedActionLog campaign={self.meta_campaign_id} via={self.executed_via}>"
