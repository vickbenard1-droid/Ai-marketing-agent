"""
CreativeConcept model.

One row per creative concept — same "individually addressable, not a JSON
array" reasoning as AdCopyVariant. The spec's "Creative Strategy" section
asks for image concepts, video concepts, hooks, visual direction, and UGC
concepts; rather than one JSON blob with 5 keys (which would make "here
are 3 image concept options" awkward — arrays-of-arrays inside JSON), each
distinct concept is its own row with a concept_type discriminator, so
"give me 3 image concepts and 2 video concepts" is just 5 rows.
"""
from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.campaign import Campaign


class CreativeConceptType(str, enum.Enum):
    IMAGE = "image"
    VIDEO = "video"
    HOOK = "hook"
    VISUAL_DIRECTION = "visual_direction"
    UGC = "ugc"


class CreativeConcept(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "creative_concepts"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )

    concept_type: Mapped[CreativeConceptType] = mapped_column(
        Enum(CreativeConceptType, name="creative_concept_type"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="creative_concepts")

    def __repr__(self) -> str:
        return f"<CreativeConcept {self.concept_type} campaign={self.campaign_id}>"
