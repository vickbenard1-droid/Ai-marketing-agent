"""
ScheduledPost model.

The content calendar's core row: one piece of Content, scheduled (or
already published, or failed) to one ConnectedAccount at a specific time.
A single Content item can be scheduled to multiple platforms/times via
multiple ScheduledPost rows - the calendar shows ScheduledPost rows, not
Content rows directly, since "the same caption going out on 3 platforms
at 3 different times" is 3 calendar entries, not 1.

status lifecycle: DRAFT (created, not yet scheduled - e.g. while a person
is still picking a time) -> SCHEDULED (has a scheduled_for time, queued
for the publishing pipeline) -> PUBLISHING (a Celery task has picked it
up) -> PUBLISHED | FAILED. FAILED posts can be retried (see
app/publishing/service.py::retry_failed_post), which moves them back to
SCHEDULED for the next pipeline pass rather than mutating a PUBLISHED
row's history.

AI recommendation fields (ai_recommended_*) are stored SEPARATELY from
the fields that actually control publishing (platform via the connected
account, scheduled_for, Content.body) - see the ai_recommended_* column
comments. This is the concrete mechanism behind the spec's "clearly
labeled as predictions rather than guaranteed results": a recommendation
sits in its own read-only-to-the-pipeline columns, and a human (or an
explicit "accept recommendation" action - see
app/scheduling/service.py::accept_ai_recommendation) must copy a value
into the real scheduling fields before it has any effect. The AI can
never silently become the thing that actually schedules a post.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin
from app.models.business_profile import StringList

if TYPE_CHECKING:
    from app.models.connected_account import ConnectedAccount
    from app.models.content import Content
    from app.models.organization import Organization
    from app.models.publishing_log import PublishingLog
    from app.models.user import User


class ScheduledPostStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


class ScheduledPost(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "scheduled_posts"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    content_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    connected_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("connected_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    status: Mapped[ScheduledPostStatus] = mapped_column(
        Enum(ScheduledPostStatus, name="scheduled_post_status"),
        nullable=False,
        default=ScheduledPostStatus.DRAFT,
    )

    scheduled_for: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    external_post_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    external_post_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    ai_recommended_post_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ai_recommended_platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ai_recommended_format: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ai_recommended_hashtags: Mapped[Optional[list[str]]] = mapped_column(StringList, nullable=True)
    ai_recommendation_rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization")
    created_by: Mapped[Optional["User"]] = relationship("User")
    content: Mapped["Content"] = relationship("Content")
    connected_account: Mapped["ConnectedAccount"] = relationship("ConnectedAccount")
    publishing_logs: Mapped[List["PublishingLog"]] = relationship(
        "PublishingLog", back_populates="scheduled_post", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ScheduledPost {self.status} org={self.organization_id}>"
