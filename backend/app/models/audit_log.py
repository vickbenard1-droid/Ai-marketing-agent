"""
AuditLog model.

Records who did what, when, in which organization. Written to on every
sensitive mutation (auth events, member/role changes, integration changes,
and — critically for later weeks — any autonomous AI optimization action).

metadata_json stores action-specific structured detail (e.g. old/new values)
without needing a new column per action type.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class AuditLog(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "audit_logs"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Nullable: some actions are system/agent-initiated, not user-initiated.
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    action: Mapped[str] = mapped_column(String(100), nullable=False)         # e.g. "member.role_changed"
    resource_type: Mapped[str] = mapped_column(String(100), nullable=True)   # e.g. "OrganizationMember"
    resource_id: Mapped[str] = mapped_column(String(255), nullable=True)

    ip_address: Mapped[str] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="audit_logs")
    actor_user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} org={self.organization_id}>"
