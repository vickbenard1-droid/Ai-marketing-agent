"""
LeadFollowUp model.

FollowUpChannel covers all 4 spec-named channels, but only EMAIL has a
real send path (reusing Week 1's SMTP infrastructure). WhatsApp/SMS/CRM
are architecture-only - a real record is created for any channel, but
send_follow_up() only actually sends for EMAIL; other channels raise a
clear error rather than fake success.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.lead import Lead
    from app.models.organization import Organization


class FollowUpChannel(str, enum.Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    SMS = "sms"
    CRM = "crm"


class FollowUpStatus(str, enum.Enum):
    DRAFTED = "drafted"
    SENT = "sent"
    FAILED = "failed"
    NOT_SENDABLE = "not_sendable"


class LeadFollowUp(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "lead_follow_ups"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[FollowUpChannel] = mapped_column(Enum(FollowUpChannel, name="followup_channel"), nullable=False)
    subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[FollowUpStatus] = mapped_column(Enum(FollowUpStatus, name="followup_status"), nullable=False, default=FollowUpStatus.DRAFTED)
    send_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    organization: Mapped["Organization"] = relationship("Organization")
    lead: Mapped["Lead"] = relationship("Lead")
