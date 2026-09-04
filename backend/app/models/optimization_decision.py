"""
OptimizationDecision model.

The exact record shape the spec requires: Observation, Evidence,
Proposed action, Expected outcome, Confidence, Risk, Required
permission - stored for EVERY decision the agent reaches, regardless of
autonomy level or whether anything is ever executed.

evidence_json is structured data (real MetricSnapshot/rollup numbers),
never free text - so a person or a later audit can verify the decision
was actually grounded in real data.

confidence is the AI's own self-assessed value, NOT a calibrated
statistical probability - this app has no historical-outcome dataset to
calibrate one from.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.approval_request import ApprovalRequest
    from app.models.meta_campaign import MetaCampaign
    from app.models.organization import Organization


class OptimizationActionType(str, enum.Enum):
    PAUSE_AD = "pause_ad"
    REDUCE_BUDGET = "reduce_budget"
    INCREASE_BUDGET = "increase_budget"
    CHANGE_AUDIENCE = "change_audience"
    CREATE_NEW_CREATIVE = "create_new_creative"
    CHANGE_HEADLINE = "change_headline"
    CHANGE_CTA = "change_cta"
    DUPLICATE_WINNING_VARIATION = "duplicate_winning_variation"
    START_RETARGETING = "start_retargeting"
    CHANGE_CAMPAIGN_STRUCTURE = "change_campaign_structure"


class DecisionRisk(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DecisionStatus(str, enum.Enum):
    RECOMMENDED = "recommended"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"
    EXECUTED = "executed"
    EXECUTION_FAILED = "execution_failed"
    EXPIRED = "expired"


class OptimizationDecision(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "optimization_decisions"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    meta_campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meta_campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )

    observation: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    action_type: Mapped[OptimizationActionType] = mapped_column(
        Enum(OptimizationActionType, name="optimization_action_type"), nullable=False
    )
    proposed_action: Mapped[str] = mapped_column(Text, nullable=False)
    action_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    expected_outcome: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    risk: Mapped[DecisionRisk] = mapped_column(Enum(DecisionRisk, name="decision_risk"), nullable=False)
    required_permission: Mapped[str] = mapped_column(String(100), nullable=False)

    status: Mapped[DecisionStatus] = mapped_column(
        Enum(DecisionStatus, name="decision_status"), nullable=False, default=DecisionStatus.RECOMMENDED
    )
    resulting_approval_request_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approval_requests.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    outcome_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    outcome_recorded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    organization: Mapped["Organization"] = relationship("Organization")
    meta_campaign: Mapped["MetaCampaign"] = relationship("MetaCampaign")
    resulting_approval_request: Mapped[Optional["ApprovalRequest"]] = relationship("ApprovalRequest")

    def __repr__(self) -> str:
        return f"<OptimizationDecision {self.action_type} campaign={self.meta_campaign_id} status={self.status}>"
