"""
Experiment model.

Represents an A/B test configuration for a campaign: which dimension is
being tested (audience, headline, hook, or creative — see
ExperimentDimension) and which specific rows are the variants under test.
variant_ids is a JSON array of UUIDs (as strings) rather than a proper
many-to-many join table — deliberate for this week: an experiment's
variant set is written once at creation and read as a whole (the
experiment UI always shows "all variants in this test" together, never
queries "which experiments include variant X"), so a join table would add
schema weight without an access pattern that needs it. If a future week
needs to query experiments by variant, this is the seam to convert.

This models the *configuration* of a test, not results — there's no
results/winner field, because no campaign has ever actually run (see
Campaign's own docstring: nothing in this app launches to a real ad
platform yet). Recording results is naturally a later week's addition
once there's real performance data to attach.
"""
from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.campaign import Campaign


class ExperimentDimension(str, enum.Enum):
    AUDIENCE = "audience"
    HEADLINE = "headline"
    HOOK = "hook"
    CREATIVE = "creative"


class Experiment(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "experiments"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    dimension: Mapped[ExperimentDimension] = mapped_column(
        Enum(ExperimentDimension, name="experiment_dimension"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=True)

    # UUIDs (as strings) of the AdCopyVariant/CreativeConcept rows, or
    # freeform audience-description strings, being tested against each
    # other — shape depends on `dimension`. See module docstring for why
    # this is JSON rather than a join table.
    variant_ids: Mapped[list] = mapped_column(JSON, nullable=False)

    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="experiments")

    def __repr__(self) -> str:
        return f"<Experiment {self.name} ({self.dimension}) campaign={self.campaign_id}>"
