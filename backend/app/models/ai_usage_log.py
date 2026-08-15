"""
AIUsageLog model.

One row per AI provider call (agent run or chat turn). This is the backing
data for token/cost tracking and usage dashboards — every call to
app.ai_providers.AIProvider.generate() that goes through
app.ai_usage.service.record_usage() gets logged here, success or failure.

Deliberately NOT reusing AuditLog for this: AuditLog is for "who did what"
security/compliance history with a small, fixed set of actions; AI usage
is high-volume, numeric, and queried very differently (sum tokens/cost
over a time range, group by agent or provider) — forcing it through
AuditLog's generic metadata_json would make those aggregate queries
painful. A dedicated table with typed numeric columns is the right shape.
"""
from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class AIUsageSource(str, enum.Enum):
    """What triggered this AI call — lets usage be broken down by agent
    vs. chat without needing a join to a separate agents table."""

    MARKETING_STRATEGY_AGENT = "marketing_strategy_agent"
    AUDIENCE_RESEARCH_AGENT = "audience_research_agent"
    AD_COPY_AGENT = "ad_copy_agent"
    SEO_AGENT = "seo_agent"
    CHAT = "chat"
    CAMPAIGN_BUILDER = "campaign_builder"
    CONTENT_GENERATION = "content_generation"
    IMAGE_ANALYSIS = "image_analysis"
    POSTING_RECOMMENDATION = "posting_recommendation"


class AIUsageLog(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "ai_usage_logs"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    source: Mapped[AIUsageSource] = mapped_column(Enum(AIUsageSource, name="ai_usage_source"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # "anthropic" | "openai"
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Nullable: an unpriced model (see ai_providers/factory.py::estimate_cost_usd)
    # logs real token counts with a null cost rather than a misleading 0.0.
    estimated_cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization")
    actor_user: Mapped[Optional["User"]] = relationship("User")

    def __repr__(self) -> str:
        return f"<AIUsageLog {self.source} {self.provider}/{self.model} org={self.organization_id}>"
