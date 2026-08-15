"""
User model.

A User is a global identity (can belong to multiple Organizations via
OrganizationMember — this is what makes agency/multi-client use cases work:
one person, many orgs, different role per org).
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.organization import OrganizationMember
    from app.models.audit_log import AuditLog
    from app.models.email_token import EmailToken


class User(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=True)

    # --- Profile (Week 2) ---
    # All nullable: profile completion is optional, never blocks login/use.
    avatar_url: Mapped[str] = mapped_column(String(1000), nullable=True)
    phone: Mapped[str] = mapped_column(String(50), nullable=True)
    timezone: Mapped[str] = mapped_column(String(100), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    memberships: Mapped[List["OrganizationMember"]] = relationship(
        "OrganizationMember", back_populates="user", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog", back_populates="actor_user"
    )
    email_tokens: Mapped[List["EmailToken"]] = relationship(
        "EmailToken", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"
