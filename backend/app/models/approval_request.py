"""
ApprovalRequest model.

Week 3 explicitly forbids any AI action that spends money or takes effect
automatically — every agent in this release only produces recommendations
(see app/agents/*.py, all of which return AgentResult with
requires_human_approval left at its default). This table is the
architecture for the future week where an agent *can* propose a concrete
action (e.g. "increase this campaign's daily budget by $50", "publish this
post") — it stores the proposed action and its status, but nothing in this
codebase ever transitions a row to EXECUTED yet. That execution step is
intentionally not built: adding it later means writing the code that
performs the approved action and flips the status, not redesigning how
approvals are requested, stored, or reviewed.

action_payload is a JSON blob rather than typed columns because the shape
of "a proposed action" varies enormously by agent (a budget change looks
nothing like a post to publish) — this mirrors the same tradeoff already
made for ConnectedAccount.encrypted_credentials and AuditLog.metadata_json
elsewhere in this codebase.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"  # reserved for a future week — see module docstring
    EXPIRED = "expired"


class ApprovalActionType(str, enum.Enum):
    """
    Closed set rather than a free-text string, so a future executor can
    switch on this safely instead of parsing action_payload blindly to
    figure out what kind of action it's looking at.
    """

    CAMPAIGN_BUDGET_CHANGE = "campaign_budget_change"
    CAMPAIGN_PAUSE = "campaign_pause"
    CAMPAIGN_LAUNCH = "campaign_launch"
    CONTENT_PUBLISH = "content_publish"
    AD_COPY_DEPLOY = "ad_copy_deploy"


class ApprovalRequest(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "approval_requests"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    action_type: Mapped[ApprovalActionType] = mapped_column(
        Enum(ApprovalActionType, name="approval_action_type"), nullable=False
    )
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus, name="approval_status"), nullable=False, default=ApprovalStatus.PENDING
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # The concrete, machine-actionable proposal — e.g.
    # {"campaign_id": "...", "new_daily_budget_cents": 5000}. A future
    # executor reads this to actually perform the action once approved.
    action_payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization")
    requested_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[requested_by_user_id])
    reviewed_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[reviewed_by_user_id])

    def __repr__(self) -> str:
        return f"<ApprovalRequest {self.action_type} {self.status} org={self.organization_id}>"
