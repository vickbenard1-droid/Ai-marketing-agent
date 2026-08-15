"""
Organization, Role, and OrganizationMember models.

Design notes:
- Organization is the tenant boundary. Every tenant-scoped table (Project,
  ConnectedAccount, AuditLog, and future campaign/content tables) carries an
  organization_id foreign key. Query-layer helpers should always filter by it.
- Role is intentionally its own table (not an enum) so agencies can later
  define custom roles without a migration.
- OrganizationMember is the join table carrying the per-org role, which is
  what allows one User to be e.g. "Admin" in one org and "Viewer" in another
  (the agency-with-multiple-clients case called out in the product vision).
- Organization.plan_type / is_agency are placeholders for future billing and
  agency-specific UI, not implemented this week.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.project import Project
    from app.models.connected_account import ConnectedAccount
    from app.models.audit_log import AuditLog
    from app.models.business_profile import BusinessProfile


class Organization(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    # Placeholder for future billing tiers — not enforced this week.
    plan_type: Mapped[str] = mapped_column(String(50), default="free", nullable=False)
    # Distinguishes an agency (manages multiple clients) from a single business.
    is_agency: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    members: Mapped[List["OrganizationMember"]] = relationship(
        "OrganizationMember", back_populates="organization", cascade="all, delete-orphan"
    )
    projects: Mapped[List["Project"]] = relationship(
        "Project", back_populates="organization", cascade="all, delete-orphan"
    )
    connected_accounts: Mapped[List["ConnectedAccount"]] = relationship(
        "ConnectedAccount", back_populates="organization", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog", back_populates="organization", cascade="all, delete-orphan"
    )
    business_profile: Mapped[Optional["BusinessProfile"]] = relationship(
        "BusinessProfile", back_populates="organization", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Organization {self.slug}>"


class Role(UUIDPKMixin, TimestampMixin, Base):
    """
    System-defined roles seeded on startup: owner, admin, member, viewer.
    Kept as a table (not a Python enum) so custom/agency roles can be added
    later without a schema migration.
    """
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=True)

    # Coarse-grained permission flags for this week's RBAC foundation.
    # A full permission-matrix system can replace this later without
    # breaking the OrganizationMember relationship.
    can_manage_billing: Mapped[bool] = mapped_column(Boolean, default=False)
    can_manage_members: Mapped[bool] = mapped_column(Boolean, default=False)
    can_manage_projects: Mapped[bool] = mapped_column(Boolean, default=False)
    can_manage_integrations: Mapped[bool] = mapped_column(Boolean, default=False)
    can_execute_ai_actions: Mapped[bool] = mapped_column(Boolean, default=False)
    can_view_only: Mapped[bool] = mapped_column(Boolean, default=True)

    # Added Week 2 to distinguish Manager / Analyst / Content Manager, which
    # the original 6 flags above couldn't tell apart (all three needed
    # can_execute_ai_actions=True but for meaningfully different surfaces).
    can_manage_campaigns: Mapped[bool] = mapped_column(Boolean, default=False)
    can_manage_content: Mapped[bool] = mapped_column(Boolean, default=False)
    can_view_analytics: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self) -> str:
        return f"<Role {self.name}>"


class OrganizationMember(UUIDPKMixin, TimestampMixin, Base):
    """Join table: a User's membership + role within one Organization."""
    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_user"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False
    )

    organization: Mapped["Organization"] = relationship("Organization", back_populates="members")
    user: Mapped["User"] = relationship("User", back_populates="memberships")
    role: Mapped["Role"] = relationship("Role")

    def __repr__(self) -> str:
        return f"<OrganizationMember org={self.organization_id} user={self.user_id}>"
