"""
WooCommerce source client.

Auth is HTTP Basic with consumer_key:consumer_secret (WooCommerce's own
REST API convention, distinct from every other source client in this
app - no Bearer token, no header-based API key). No status filter is
passed to get_orders() - unlike Shopify, WooCommerce's default order
listing already includes every status (cancelled, refunded, etc.)
without needing an explicit "any" equivalent, so
app.analytics.ingestion.translate_woocommerce_orders can already see
the cancelled/refunded orders its own accounting rule depends on.
"""
from typing import Optional

import httpx


class WooCommerceApiError(Exception):
    pass


class WooCommerceAuthError(WooCommerceApiError):
    pass


class WooCommerceRateLimitError(WooCommerceApiError):
    pass


class WooCommerceClient:
    def __init__(
        self,
        *,
        store_url: str,
        consumer_key: str,
        consumer_secret: str,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self._store_url = store_url.rstrip("/")
        self._consumer_key = consumer_key
        self._consumer_secret = consumer_secret
        self._transport = transport

    def get_orders(self, *, after: str, before: str) -> list:
        with httpx.Client(base_url=self._store_url, timeout=30.0, transport=self._transport) as client:
            response = client.get(
                "/wp-json/wc/v3/orders",
                auth=(self._consumer_key, self._consumer_secret),
                params={"after": after, "before": before, "per_page": 100},
            )

        if response.status_code == 401:
            raise WooCommerceAuthError(f"WooCommerce auth failed: {response.text[:300]}")
        if response.status_code == 429:
            raise WooCommerceRateLimitError("WooCommerce rate limit exceeded")
        if response.status_code >= 400:
            raise WooCommerceApiError(f"WooCommerce API returned {response.status_code}: {response.text[:300]}")

        return response.json()
