"""
BusinessProfile model.

One-to-one with Organization, capturing the 10-step onboarding questionnaire
(business name mirrors Organization.name and isn't duplicated here — see
note below). Kept as its own table rather than columns on Organization
because:

1. Organization is the tenant/auth boundary and is touched by every
   request via get_current_org_member — keeping it lean matters.
2. Onboarding fields are optional/evolving (a future week might add more
   questions); a separate table means schema growth here doesn't touch the
   tenant-critical Organization table or its migration history.
3. onboarding_completed_at cleanly answers "has this org finished
   onboarding" for a redirect guard, without overloading Organization with
   a flag that has nothing to do with tenancy.

Note on business name: Organization.name already captures this (set at
registration or org creation) and onboarding step 1 edits that same field
via the organizations API rather than duplicating it here — see
app/api/v1/endpoints/onboarding.py.
"""
from __future__ import annotations

import enum
import json
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, TypeDecorator
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.organization import Organization


class StringList(TypeDecorator):
    """
    list[str] column that's a native Postgres ARRAY in production and a
    JSON-encoded TEXT column on any other dialect (SQLite, used by the test
    suite — see app/tests/conftest.py). Unlike postgresql.UUID/Enum, plain
    postgresql.ARRAY has no automatic SQLite fallback, so this exists to
    keep the model Postgres-native while still being testable without a
    live Postgres instance.
    """

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_ARRAY(String(50)))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return json.loads(value)


class MarketingGoal(str, enum.Enum):
    SALES = "sales"
    LEADS = "leads"
    WEBSITE_TRAFFIC = "website_traffic"
    BRAND_AWARENESS = "brand_awareness"


class BrandVoice(str, enum.Enum):
    """
    The 8 preset voices from the Week 5 spec, plus CUSTOM for a
    business-written description that doesn't fit a preset. When
    brand_voice=CUSTOM, brand_voice_custom holds the actual text; for any
    preset value, brand_voice_custom is ignored even if set (kept rather
    than cleared on preset selection, in case the user switches back to
    Custom without retyping it).
    """

    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    LUXURY = "luxury"
    EDUCATIONAL = "educational"
    FUNNY = "funny"
    BOLD = "bold"
    INSPIRATIONAL = "inspirational"
    CUSTOM = "custom"


class BusinessProfile(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "business_profiles"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # enforces one-to-one at the DB level
        index=True,
    )

    # Step 2-6
    website_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)  # ISO 3166-1 alpha-2
    products_services: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_customers: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Step 7
    marketing_goal: Mapped[Optional[MarketingGoal]] = mapped_column(
        Enum(MarketingGoal, name="marketing_goal"), nullable=True
    )

    # Step 8 — stored as a whole-currency-unit integer. This is a
    # self-reported planning budget, not a ledger amount, so a plain
    # integer keeps the onboarding UI simple. Revisit if this ever feeds
    # billing.
    monthly_ad_budget: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    budget_currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)

    # Step 9-10 — free-form lists of platform names. Kept as string arrays
    # rather than FKs to a "platforms" table: this is what the business
    # *says* it uses, captured during onboarding, not a live integration
    # (that's ConnectedAccount, a separate concern — see
    # app/models/connected_account.py).
    social_platforms: Mapped[Optional[list[str]]] = mapped_column(StringList, nullable=True)
    advertising_platforms: Mapped[Optional[list[str]]] = mapped_column(StringList, nullable=True)

    onboarding_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Tracks which step the user last completed (1-10), so a refresh mid-
    # onboarding resumes at the right step instead of restarting.
    onboarding_current_step: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # --- Week 5: brand voice ---
    # Configured separately from the 10-step onboarding wizard (not step
    # 11) — brand voice is a content-generation setting a business is
    # more likely to revisit/change over time than the one-time onboarding
    # answers above, so it gets its own settings surface
    # (app/api/v1/endpoints/business_profile.py) rather than being locked
    # into the wizard's linear flow.
    brand_voice: Mapped[Optional[BrandVoice]] = mapped_column(
        Enum(BrandVoice, name="brand_voice"), nullable=True
    )
    brand_voice_custom: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="business_profile"
    )

    def __repr__(self) -> str:
        return f"<BusinessProfile org={self.organization_id}>"
