"""
PublishingLog model.

An append-only row per publish ATTEMPT against a ScheduledPost - not the
same as the post's current status. A post retried twice before finally
succeeding has 3 PublishingLog rows (2 failures, 1 success) but the
ScheduledPost itself only ever shows its current state. This is what
satisfies the spec's explicit "publishing logs" requirement as its own
concept, distinct from the calendar/status view: a business can see
exactly what happened on each attempt (when, what error, which platform
response), not just "it's currently failed."

Never stores anything from ConnectedAccount.encrypted_credentials or any
decrypted token - request_summary is deliberately a short, human-readable
description (e.g. "POST to Graph API /me/feed") for debugging, not a raw
request/response dump that could leak a token into a log a wider set of
roles can read than should ever see a credential.
"""
from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.scheduled_post import ScheduledPost


class PublishingLogOutcome(str, enum.Enum):
    SUCCESS = "success"
    FAILURE = "failure"


class PublishingLog(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "publishing_logs"

    scheduled_post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scheduled_posts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    outcome: Mapped[PublishingLogOutcome] = mapped_column(
        Enum(PublishingLogOutcome, name="publishing_log_outcome"), nullable=False
    )
    request_summary: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempt_number: Mapped[int] = mapped_column(nullable=False)

    scheduled_post: Mapped["ScheduledPost"] = relationship("ScheduledPost", back_populates="publishing_logs")

    def __repr__(self) -> str:
        return f"<PublishingLog {self.outcome} attempt={self.attempt_number}>"
