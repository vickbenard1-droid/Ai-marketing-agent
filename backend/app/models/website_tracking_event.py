"""WebsiteTrackingEvent model - real page-view and conversion events from
the public tracking pixel, keyed by a browser-generated visitor_id."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, BigInteger, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.organization import Organization


class WebsiteTrackingEventType(str, enum.Enum):
    PAGE_VIEW = "page_view"
    CONVERSION = "conversion"


class WebsiteTrackingEvent(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "website_tracking_events"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[WebsiteTrackingEventType] = mapped_column(
        Enum(WebsiteTrackingEventType, name="website_tracking_event_type"), nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    visitor_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    page_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    utm_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    conversion_type_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    conversion_value_cents: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self) -> str:
        return f"<WebsiteTrackingEvent {self.event_type} visitor={self.visitor_id}>"
