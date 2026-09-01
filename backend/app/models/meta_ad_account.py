"""
MetaAdAccount model.

A ConnectedAccount (app.models.connected_account) represents ONE OAuth
grant - a person authorized this app to act as them on Meta. A single
Meta user can have access to MULTIPLE ad accounts (personal, agency
clients, multiple businesses), so MetaAdAccount is a separate,
one-to-many child: one ConnectedAccount can have many MetaAdAccount
rows, each representing a real, distinct Meta ad account this
organization has chosen to actually connect and use in this app.

Nothing in this app is permitted to spend against a MetaAdAccount
without a corresponding AdAccountSpendLimit row - see that model's own
docstring for the mandatory, fail-closed reasoning.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.connected_account import ConnectedAccount
    from app.models.organization import Organization


class MetaAdAccount(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "meta_ad_accounts"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    connected_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("connected_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    external_ad_account_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    timezone_name: Mapped[str] = mapped_column(String(64), nullable=False)

    organization: Mapped["Organization"] = relationship("Organization")
    connected_account: Mapped["ConnectedAccount"] = relationship("ConnectedAccount")

    def __repr__(self) -> str:
        return f"<MetaAdAccount {self.external_ad_account_id} {self.name}>"
