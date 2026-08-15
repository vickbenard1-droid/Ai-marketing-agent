"""
Campaign model.

Holds every input collected by the campaign builder wizard (see
docs/ARCHITECTURE.md "Week 4") plus a status field tracking the draft's
lifecycle. Organization-scoped, matching every other tenant-scoped table
in this app — not project-scoped, since no Project CRUD API exists yet
(same reasoning as app/agents/base.py::AgentContext).

status transitions: DRAFT (inputs being collected) -> GENERATING (AI call
in flight) -> GENERATED (strategy/audience/copy/creative/budget produced,
editable) -> APPROVED (human has reviewed and approved the draft). There
is no LAUNCHED status — this app never launches a campaign to a real ad
platform (see product spec "Do NOT launch campaigns yet"). Approving a
campaign here is a lightweight status change, deliberately NOT routed
through ApprovalRequest: ApprovalRequest exists for actions with real
external side effects (see its own docstring), and approving a draft has
none — it just means a human has reviewed the AI's output. If a future
week adds real launch capability, *that* action would create an
ApprovalRequest with action_type=CAMPAIGN_LAUNCH; this status field would
stay exactly as it is.

Money fields (product_price, budget) are stored as plain integers in
whole currency units, not minor units (cents) — see budget_amount's own
comment. This mirrors BusinessProfile.monthly_ad_budget's existing
precedent (a self-reported planning number, not a ledger amount) rather
than introducing a different convention for campaign money fields.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User
    from app.models.campaign_strategy import CampaignStrategy
    from app.models.ad_copy_variant import AdCopyVariant
    from app.models.creative_concept import CreativeConcept
    from app.models.experiment import Experiment


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    GENERATING = "generating"
    GENERATED = "generated"
    APPROVED = "approved"


class MarketingObjective(str, enum.Enum):
    """
    Reuses the same 4 objectives as BusinessProfile.MarketingGoal
    (sales/leads/website_traffic/brand_awareness) rather than introducing
    a parallel enum — a campaign's objective is the same concept at a
    more specific scope, and keeping the value set identical means the
    campaign wizard can default step 3 from the org's onboarding answer
    without a translation table between two different enums.
    """

    SALES = "sales"
    LEADS = "leads"
    WEBSITE_TRAFFIC = "website_traffic"
    BRAND_AWARENESS = "brand_awareness"


class Campaign(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "campaigns"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus, name="campaign_status"), nullable=False, default=CampaignStatus.DRAFT
    )

    # --- Wizard step 2: Product ---
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Self-reported planning price, whole currency units — see module
    # docstring. Nullable: a service-based business may not have one
    # fixed "price" (e.g. "school admission forms" pricing may vary).
    product_price: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    product_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Wizard step 4: Audience ---
    target_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    target_audience: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    existing_customer_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Wizard step 3: Objective ---
    objective: Mapped[MarketingObjective] = mapped_column(
        Enum(MarketingObjective, name="campaign_objective"), nullable=False
    )
    desired_outcome_count: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )  # e.g. "100" in "100 qualified leads"

    # --- Wizard step 5: Budget ---
    budget_amount: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    budget_currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    duration_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # --- Wizard step 6: Creative input ---
    landing_page_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    organization: Mapped["Organization"] = relationship("Organization")
    created_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by_user_id])
    approved_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[approved_by_user_id])

    strategy: Mapped[Optional["CampaignStrategy"]] = relationship(
        "CampaignStrategy", back_populates="campaign", uselist=False, cascade="all, delete-orphan"
    )
    ad_copy_variants: Mapped[List["AdCopyVariant"]] = relationship(
        "AdCopyVariant", back_populates="campaign", cascade="all, delete-orphan"
    )
    creative_concepts: Mapped[List["CreativeConcept"]] = relationship(
        "CreativeConcept", back_populates="campaign", cascade="all, delete-orphan"
    )
    experiments: Mapped[List["Experiment"]] = relationship(
        "Experiment", back_populates="campaign", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Campaign {self.product_name} ({self.status}) org={self.organization_id}>"
