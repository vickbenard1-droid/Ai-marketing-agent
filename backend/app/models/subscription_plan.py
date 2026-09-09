"""
SubscriptionPlan model.

The spec's 4 tiers (Free/Starter/Professional/Agency), each with real,
enforceable usage limits for the spec's 5 named categories: AI usage
(monthly token budget), campaigns, connected accounts, content
generation (monthly), automated actions (monthly).

Deliberately a real DATABASE TABLE, not a hardcoded enum/dict - the
spec's own tier names/limits are a reasonable starting default, seeded
once (see app.db.seed_plans), but a real SaaS needs to be able to
change pricing/limits without a code deploy. Every field that can be
None means "unlimited" for that category (used by Agency) - never 0,
which would mean "no usage permitted at all," a materially different
and dangerous-to-conflate meaning.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin


class SubscriptionPlan(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "subscription_plans"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    monthly_price_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    max_ai_tokens_per_month: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_campaigns: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_connected_accounts: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_content_generations_per_month: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_automated_actions_per_month: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<SubscriptionPlan {self.name}>"
