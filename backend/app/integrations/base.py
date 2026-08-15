"""
Integration provider interface — foundation only.

NOT IMPLEMENTED YET: Meta Ads, Google Ads, TikTok Ads, LinkedIn, Instagram,
Facebook, YouTube, WordPress, Shopify, WooCommerce, Google Analytics,
Google Search Console.

Each future integration will subclass IntegrationProvider and implement
OAuth connect/refresh and basic read/write operations against the
ConnectedAccount row for that platform.
"""
from abc import ABC, abstractmethod

from app.models.connected_account import ConnectedAccount, PlatformType


class IntegrationProvider(ABC):
    platform: PlatformType

    @abstractmethod
    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        """Return the OAuth URL the frontend should redirect the user to."""
        raise NotImplementedError

    @abstractmethod
    def exchange_code_for_credentials(self, code: str, redirect_uri: str) -> dict:
        """Exchange an OAuth code for tokens. Returned dict is encrypted before storage."""
        raise NotImplementedError

    @abstractmethod
    def test_connection(self, account: ConnectedAccount) -> bool:
        """Verify stored credentials still work."""
        raise NotImplementedError
