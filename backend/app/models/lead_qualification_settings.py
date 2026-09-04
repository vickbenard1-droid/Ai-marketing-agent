"""LeadQualificationSettings model - one row per org, the business-rule criteria for what counts as qualified."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.organization import Organization


class LeadQualificationSettings(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "lead_qualification_settings"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    minimum_score: Mapped[int] = mapped_column(Integer, nullable=False, default=40)
    minimum_disclosed_budget_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    require_product_interest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    organization: Mapped["Organization"] = relationship("Organization")
