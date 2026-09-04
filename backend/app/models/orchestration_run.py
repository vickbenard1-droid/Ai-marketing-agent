"""
OrchestrationRun model.

One row per top-level goal the person gives the orchestrator (e.g. "help
me get 100 sales for my product") - the plan_json is the ordered list of
steps the orchestrator decided on (spec's 14-step example), current_step
tracks progress through it, and every AgentActivityLog row for this run
links back here via orchestration_run_id.

status=PAUSED_FOR_APPROVAL is the concrete mechanism behind "the user
must remain in control" - the orchestrator does not proceed past a
step requiring approval on its own; a person must act (see
app/orchestrator/service.py::advance_run).
"""
from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, Enum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class OrchestrationRunStatus(str, enum.Enum):
    PLANNING = "planning"
    RUNNING = "running"
    PAUSED_FOR_APPROVAL = "paused_for_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OrchestrationRun(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "orchestration_runs"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    goal_text: Mapped[str] = mapped_column(Text, nullable=False)
    plan_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[OrchestrationRunStatus] = mapped_column(Enum(OrchestrationRunStatus, name="orchestration_run_status"), nullable=False, default=OrchestrationRunStatus.PLANNING)
    final_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization")
    requested_by: Mapped[Optional["User"]] = relationship("User")

    def __repr__(self) -> str:
        return f"<OrchestrationRun goal={self.goal_text[:40]!r} status={self.status}>"
