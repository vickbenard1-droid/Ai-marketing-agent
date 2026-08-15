"""
RevokedToken model.

Backs logout: JWTs are stateless by design (see app/core/security.py), so
"logging out" a refresh token means recording its `jti` here and checking
this table on every /auth/refresh call. Only refresh token jtis are ever
revoked — access tokens are short-lived (30 min default) and not checked
against this table on every request, which would defeat the point of using
a stateless token for the high-frequency case. This is the standard
"stateless access token + stateless-but-checked refresh token" tradeoff.

expires_at mirrors the original token's expiry so a cleanup job (not built
this week) can safely prune rows for tokens that would have expired anyway.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin


class RevokedToken(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:
        return f"<RevokedToken jti={self.jti}>"
