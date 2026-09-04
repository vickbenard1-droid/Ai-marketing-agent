"""
LeadStageTransition model.

Append-only history of every stage change - Lead.stage only ever holds
the current stage; this table makes "how long did this lead spend in
each stage" answerable from real data.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin
from app.models.lead import LeadStage

if TYPE_CHECKING:
    from app.models.lead import Lead
    from app.models.user import User


class LeadStageTransition(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "lead_stage_transitions"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_stage: Mapped[Optional[LeadStage]] = mapped_column(Enum(LeadStage, name="lead_stage"), nullable=True)
    to_stage: Mapped[LeadStage] = mapped_column(Enum(LeadStage, name="lead_stage"), nullable=False)
    changed_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    lead: Mapped["Lead"] = relationship("Lead")
    changed_by: Mapped[Optional["User"]] = relationship("User")

    def __repr__(self) -> str:
        return f"<LeadStageTransition lead={self.lead_id} {self.from_stage}->{self.to_stage}>"
