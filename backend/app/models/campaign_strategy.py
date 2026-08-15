"""
CampaignStrategy model.

One-to-one with Campaign. Holds the two structured sections the spec
calls "Campaign Strategy" and "Audience Strategy" — kept as JSON blobs
(strategy_json, audience_json) rather than a dozen more typed columns,
for the same reason ApprovalRequest.action_payload and
AuditLog.metadata_json are JSON: the AI's output shape is inherently
semi-structured prose-with-sections (e.g. "pain points" is naturally a
list of short strings, "value proposition" is a paragraph), and forcing
every sub-field into its own column would make the parsing layer
(app/campaigns/generation_service.py) more brittle, not less — a missing
or reworded sub-key degrades gracefully as a missing dict key rather than
a failed column write.

budget_strategy_json is the third structured section ("Budget Strategy")
from the spec — test budget, ad set count, allocation, testing period,
scaling rules. It lives here rather than as its own table because it's
generated in the same AI call and edited as a unit, same as strategy and
audience.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.campaign import Campaign


class CampaignStrategy(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "campaign_strategies"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # enforces one-to-one at the DB level, same pattern as BusinessProfile
        index=True,
    )

    # Shape (all keys optional — the parser fills what the model returned):
    # {"objective": str, "funnel_stage": str, "target_customer": str,
    #  "pain_points": [str], "value_proposition": str, "offer": str, "cta": str}
    strategy_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Shape:
    # {"demographics": str, "geography": str, "interests": [str],
    #  "behaviors": [str], "lookalike_strategy": str, "retargeting_strategy": str}
    audience_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Shape:
    # {"test_budget": str, "ad_set_count": int, "budget_allocation": str,
    #  "testing_period_days": int, "scaling_rules": str}
    budget_strategy_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="strategy")

    def __repr__(self) -> str:
        return f"<CampaignStrategy campaign={self.campaign_id}>"
