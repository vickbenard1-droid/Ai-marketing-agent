"""
AgentDecision model.

The spec's "memory of previous decisions" - one row per decision any
agent (or the orchestrator itself) makes, independent of whether that
decision was ever executed. Deliberately NOT the same table as
OptimizationDecision (Week 9, Meta-campaign-specific) or
AgentActivityLog (this week's observability timeline, UI-facing) -
AgentDecision is the durable memory record an agent can query later
("what did we decide last time for this kind of goal"), while
AgentActivityLog is the human-facing "what happened and when" feed.
A given real decision may have rows in both, linked by
resulting_activity_log_id.
"""
from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.organization import Organization


class DecisionOutcome(str, enum.Enum):
    PENDING = "pending"
    SUCCESSFUL = "successful"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"


class AgentDecision(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "agent_decisions"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_name: Mapped[str] = mapped_column(Text, nullable=False)
    goal_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decision_summary: Mapped[str] = mapped_column(Text, nullable=False)
    context_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    outcome: Mapped[DecisionOutcome] = mapped_column(Enum(DecisionOutcome, name="decision_outcome"), nullable=False, default=DecisionOutcome.PENDING)
    outcome_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self) -> str:
        return f"<AgentDecision {self.agent_name} outcome={self.outcome}>"
