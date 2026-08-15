"""
ConnectedAccount model.

Represents a link to an external platform (Meta Ads, Google Ads, TikTok,
LinkedIn, WordPress, Shopify, GA4, Search Console, etc.). Only the schema is
defined this week — no real OAuth flows or API clients are implemented yet.

Credentials are stored encrypted (see app.core.security.encrypt_secret) and
are NEVER returned to the frontend in plaintext.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.project import Project


class PlatformType(str, enum.Enum):
    """Extend this enum as new integrations are built — no other schema change needed."""
    META_ADS = "meta_ads"
    GOOGLE_ADS = "google_ads"
    TIKTOK_ADS = "tiktok_ads"
    LINKEDIN = "linkedin"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    YOUTUBE = "youtube"
    WORDPRESS = "wordpress"
    SHOPIFY = "shopify"
    WOOCOMMERCE = "woocommerce"
    GOOGLE_ANALYTICS = "google_analytics"
    GOOGLE_SEARCH_CONSOLE = "google_search_console"

    # --- Week 6: organic social posting connections ---
    # Deliberately distinct from the ad-account values above even where
    # the vendor overlaps (e.g. FACEBOOK_PAGE vs META_ADS both belong to
    # Meta) — an ads account and a Page/Profile connection use different
    # OAuth scopes, different Graph API endpoints, and are fundamentally
    # different capabilities from this app's point of view: one lets you
    # spend money on ads, the other lets you publish organic posts. A
    # business could reasonably connect one without the other.
    FACEBOOK_PAGE = "facebook_page"
    INSTAGRAM_BUSINESS = "instagram_business"
    LINKEDIN_PAGE = "linkedin_page"
    X_ACCOUNT = "x_account"
    TIKTOK_ACCOUNT = "tiktok_account"
    YOUTUBE_CHANNEL = "youtube_channel"


ORGANIC_SOCIAL_PLATFORMS = {
    PlatformType.FACEBOOK_PAGE,
    PlatformType.INSTAGRAM_BUSINESS,
    PlatformType.LINKEDIN_PAGE,
    PlatformType.X_ACCOUNT,
    PlatformType.TIKTOK_ACCOUNT,
    PlatformType.YOUTUBE_CHANNEL,
}


class ConnectionStatus(str, enum.Enum):
    PENDING = "pending"
    CONNECTED = "connected"
    EXPIRED = "expired"
    ERROR = "error"
    DISCONNECTED = "disconnected"


class ConnectedAccount(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "connected_accounts"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )

    platform: Mapped[PlatformType] = mapped_column(Enum(PlatformType, name="platform_type"), nullable=False)
    status: Mapped[ConnectionStatus] = mapped_column(
        Enum(ConnectionStatus, name="connection_status"), default=ConnectionStatus.PENDING, nullable=False
    )

    external_account_id: Mapped[str] = mapped_column(String(255), nullable=True)
    external_account_name: Mapped[str] = mapped_column(String(255), nullable=True)

    # Encrypted blob (Fernet) — access tokens / refresh tokens / API keys.
    # Never selected into a Pydantic response schema.
    encrypted_credentials: Mapped[str] = mapped_column(Text, nullable=True)

    # When the access token expires, if the platform told us — drives the
    # "credentials expired, please reauthorize" flow (see
    # app/oauth/service.py::list_accounts_needing_reauth). Nullable
    # because not every platform's OAuth response includes an expiry
    # (some issue long-lived or non-expiring tokens).
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Space-separated OAuth scopes actually granted by the platform —
    # kept separate from whatever scopes we requested, since a person can
    # deny individual permissions during the platform's consent screen
    # and grant fewer than requested. Surfaced read-only in the connected
    # account list so a business can see exactly what was authorized.
    granted_scopes: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    # Human-readable reason the last publish/refresh attempt against this
    # account failed, surfaced in the UI when status=ERROR. Cleared on
    # the next successful use of the account.
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="connected_accounts")
    project: Mapped["Project"] = relationship("Project", back_populates="connected_accounts")

    def __repr__(self) -> str:
        return f"<ConnectedAccount {self.platform} ({self.status})>"
