"""
OAuthState model.

The CSRF protection for the OAuth connect flow: start_connect_flow (see
app/oauth/service.py) generates a random, unguessable state value, stores
it here alongside which org/user/platform/project initiated the request,
and hands only the state value to the platform's authorize URL. On
callback, handle_callback looks up the state, verifies it exists, hasn't
expired, and hasn't already been used, then deletes/marks it used - the
same single-use-token discipline as app.models.email_token.EmailToken,
which this closely mirrors, but a distinct table rather than folding into
EmailTokenType: this token is never emailed to anyone or exposed to a
person as a link, it lives entirely in a redirect round-trip the person's
browser carries for them, so the "stored hashed to protect against a DB
leak handing out a working link" reasoning that shapes EmailToken doesn't
apply the same way here - the value itself is stored directly.

code_verifier is only populated for platforms with uses_pkce=True (see
app.oauth.base.OAuthPlatformProvider) - generated at flow-start,
persisted here since PKCE requires the *same* verifier to be presented at
both authorize and token-exchange time, and this is the only server-side
state that survives the round trip to the platform and back.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.project import Project
    from app.models.user import User


class OAuthState(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "oauth_states"

    state_value: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    initiated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    platform_type: Mapped[str] = mapped_column(String(50), nullable=False)
    code_verifier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    organization: Mapped["Organization"] = relationship("Organization")
    project: Mapped["Project"] = relationship("Project")
    initiated_by: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<OAuthState {self.platform_type} org={self.organization_id}>"
