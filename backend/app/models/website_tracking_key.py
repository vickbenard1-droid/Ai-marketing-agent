"""
WebsiteTrackingKey model.

Modeled separately from ConnectedAccount.external_account_id - a
tracking key is DELIBERATELY PUBLIC (embedded in the business's website
source, visible to anyone who views page source), a fundamentally
different confidentiality model than an OAuth access token, which must
stay secret. Reusing an existing "external account id" field for this
would blur two genuinely different security properties together.
"""
from __future__ import annotations

import secrets
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.organization import Organization


def generate_tracking_key() -> str:
    return f"wtk_{secrets.token_urlsafe(24)}"


class WebsiteTrackingKey(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "website_tracking_keys"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self) -> str:
        return f"<WebsiteTrackingKey org={self.organization_id}>"
