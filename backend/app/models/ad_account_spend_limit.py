"""
AdAccountSpendLimit model.

FAIL-CLOSED BY DESIGN: a MetaAdAccount with NO corresponding
AdAccountSpendLimit row is blocked from any spend-affecting action at
all (see app.meta_ads.spend_guard.assert_within_limits, which is the
only function permitted to authorize a spend action, and which treats a
missing row as an automatic block, not "no limit configured, allow
anything").

is_emergency_stopped is a SEPARATE code path from the numeric limit
comparisons below, deliberately - a bug in the daily_spend_limit_cents
arithmetic can never accidentally bypass an active emergency stop,
because the stop check doesn't depend on that arithmetic being correct.
The stop is reversible by any user with can_manage_integrations
permission, not restricted to an Owner role.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.meta_ad_account import MetaAdAccount
    from app.models.user import User


class AdAccountSpendLimit(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "ad_account_spend_limits"

    meta_ad_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta_ad_accounts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    daily_spend_limit_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)

    is_emergency_stopped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    emergency_stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    emergency_stopped_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    emergency_stop_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    meta_ad_account: Mapped["MetaAdAccount"] = relationship("MetaAdAccount")
    emergency_stopped_by: Mapped[Optional["User"]] = relationship("User")

    def __repr__(self) -> str:
        return f"<AdAccountSpendLimit account={self.meta_ad_account_id} daily_limit={self.daily_spend_limit_cents}>"
