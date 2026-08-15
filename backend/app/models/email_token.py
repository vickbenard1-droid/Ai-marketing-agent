"""
EmailToken model.

Backs both email verification and password reset. Chosen as one table with
a `token_type` discriminator rather than two near-identical tables — the
shape (user, opaque token, expiry, single-use) is identical for both, and
splitting them would just duplicate the "is this token valid" query logic.

Deliberately NOT a JWT: these need to be single-use (checked via `used_at`)
and individually invalidatable, which stateless JWTs don't give without a
separate revocation list anyway — so a DB-backed opaque token is simpler
here, not a workaround.

The token value itself is stored hashed (SHA-256), not plaintext, following
the same principle as password storage: a DB read (via a bug, backup leak,
etc.) should not hand out working reset/verification links.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.user import User


class EmailTokenType(str, enum.Enum):
    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"


class EmailToken(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "email_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_type: Mapped[EmailTokenType] = mapped_column(
        Enum(EmailTokenType, name="email_token_type"), nullable=False
    )
    # SHA-256 hex digest of the token sent to the user — never the raw value.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="email_tokens")

    def __repr__(self) -> str:
        return f"<EmailToken {self.token_type} user={self.user_id}>"
