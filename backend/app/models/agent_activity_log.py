"""
AgentActivityLog model.

The spec's Agent Activity timeline - every step the orchestrator or an
individual agent takes gets one row, human-facing (rendered directly in
the frontend timeline), covering exactly the 5 things the spec asks to
be shown: what the AI is doing (action_description), why
(reasoning), what data it used (data_used_json), what it recommends
(recommendation), what it executed (execution_result_json, null until
something is actually carried out).

Distinct from AuditLog (app.audit, pre-existing since Week 1) -
AuditLog is a generic "who did what to which resource" security/
compliance trail covering human AND system actions across the whole
app; AgentActivityLog is specifically the narrative trace of an agent's
own reasoning process, richer and AI-specific.
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
    from app.models.orchestration_run import OrchestrationRun
    from app.models.organization import Organization


class ActivityStatus(str, enum.Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentActivityLog(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "agent_activity_logs"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    orchestration_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orchestration_runs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    agent_name: Mapped[str] = mapped_column(Text, nullable=False)
    step_number: Mapped[Optional[int]] = mapped_column(nullable=True)

    action_description: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    data_used_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_result_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    status: Mapped[ActivityStatus] = mapped_column(Enum(ActivityStatus, name="activity_status"), nullable=False, default=ActivityStatus.PLANNED)
    requires_approval: Mapped[bool] = mapped_column(nullable=False, default=False)
    approval_request_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approval_requests.id", ondelete="SET NULL"), nullable=True
    )

    organization: Mapped["Organization"] = relationship("Organization")
    orchestration_run: Mapped[Optional["OrchestrationRun"]] = relationship("OrchestrationRun")

    def __repr__(self) -> str:
        return f"<AgentActivityLog {self.agent_name} status={self.status}>"
