"""
Lead model.

The core entity Week 10 builds around - a Lead is a PERSON moving
through a real sales process, with a mutable pipeline stage and a
mutable score, distinct from Week 8's ConversionEvent (a single
measured moment). ConversionEvent.converted_entity_type/
converted_entity_id was deliberately left loosely-typed for exactly
this reason - this model is what finally gives lead conversions a real
entity to point at.

SOURCE reuses PlatformType's vocabulary where a real overlap exists
(META_ADS, SHOPIFY, WOOCOMMERCE, WEBSITE_TRACKING, CRM already exist)
and adds LANDING_PAGE and MANUAL, the two genuinely new values.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.meta_campaign import MetaCampaign
    from app.models.organization import Organization
    from app.models.user import User


class LeadStage(str, enum.Enum):
    NEW_LEAD = "new_lead"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    INTERESTED = "interested"
    NEGOTIATION = "negotiation"
    WON = "won"
    LOST = "lost"


TERMINAL_STAGES = {LeadStage.WON, LeadStage.LOST}


class LeadSource(str, enum.Enum):
    META_LEADS = "meta_leads"
    WEBSITE_FORM = "website_form"
    LANDING_PAGE = "landing_page"
    SHOPIFY = "shopify"
    WOOCOMMERCE = "woocommerce"
    CRM = "crm"
    MANUAL = "manual"


class Lead(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "leads"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    source: Mapped[LeadSource] = mapped_column(Enum(LeadSource, name="lead_source"), nullable=False)
    source_external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    attributed_meta_campaign_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meta_campaigns.id", ondelete="SET NULL"), nullable=True
    )

    stage: Mapped[LeadStage] = mapped_column(Enum(LeadStage, name="lead_stage"), nullable=False, default=LeadStage.NEW_LEAD)

    product_interest: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    disclosed_budget_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    score_factors_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    score_computed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    assigned_to_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization")
    attributed_meta_campaign: Mapped[Optional["MetaCampaign"]] = relationship("MetaCampaign")
    assigned_to: Mapped[Optional["User"]] = relationship("User")

    def __repr__(self) -> str:
        return f"<Lead {self.email or self.full_name or self.id} stage={self.stage} source={self.source}>"
