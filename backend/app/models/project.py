"""
Project model.

A Project represents one "client/brand/website" that an Organization markets.
An agency Organization will have many Projects (one per client); a single
business Organization will typically have one. Campaigns, content, and
ConnectedAccounts will attach to a Project in future weeks.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, List

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.connected_account import ConnectedAccount


class Project(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    website_url: Mapped[str] = mapped_column(String(500), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    industry: Mapped[str] = mapped_column(String(100), nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="projects")
    connected_accounts: Mapped[List["ConnectedAccount"]] = relationship(
        "ConnectedAccount", back_populates="project", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Project {self.name}>"
