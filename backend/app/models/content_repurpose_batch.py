"""
ContentRepurposeBatch model.

Groups the outputs of one "repurpose this content" run (see
app/content/repurpose_service.py) — the spec's 5 social posts + 3 video
scripts + 1 blog + 1 email + 10 hooks all come from a single source input
and a single AI call, and this table is what lets the UI show "here's
everything that came from repurposing X" as one unit, rather than 20
unrelated Content rows with no link between them.

Stores the same source fields as Content (source_text/source_url/
source_asset_id) since the batch itself — not any individual output row —
is what was actually repurposed.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User
    from app.models.content import Content


class ContentRepurposeBatch(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "content_repurpose_batches"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    source_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    source_asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_assets.id", ondelete="SET NULL"), nullable=True
    )

    organization: Mapped["Organization"] = relationship("Organization")
    created_by: Mapped[Optional["User"]] = relationship("User")
    items: Mapped[List["Content"]] = relationship("Content", back_populates="repurpose_batch")

    def __repr__(self) -> str:
        return f"<ContentRepurposeBatch {self.id} org={self.organization_id}>"
