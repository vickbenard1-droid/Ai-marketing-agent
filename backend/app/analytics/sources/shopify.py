"""
Shopify source client.

Auth is a per-shop access token in the X-Shopify-Access-Token header
(not a Bearer token) - Shopify's own real API convention, distinct from
every other source client in this app. status="any" is used
deliberately for get_orders(): Shopify's default order-listing endpoint
excludes cancelled orders unless explicitly asked for "any" status, and
this app's own ingestion translator (app.analytics.ingestion.
translate_shopify_orders) needs to see cancelled orders to correctly
count them toward purchases while excluding them from revenue - a
default-status fetch would silently hide exactly the data that
accounting rule depends on.
"""
from typing import Optional

import httpx

SHOPIFY_API_VERSION = "2024-10"


class ShopifyApiError(Exception):
    pass


class ShopifyAuthError(ShopifyApiError):
    pass


class ShopifyRateLimitError(ShopifyApiError):
    pass


class ShopifyClient:
    def __init__(self, access_token: str, *, shop_domain: str, transport: Optional[httpx.BaseTransport] = None):
        self._access_token = access_token
        self._shop_domain = shop_domain
        self._transport = transport

    def get_orders(self, *, created_at_min: str, created_at_max: str) -> list:
        base_url = f"https://{self._shop_domain}/admin/api/{SHOPIFY_API_VERSION}"
        with httpx.Client(base_url=base_url, timeout=30.0, transport=self._transport) as client:
            response = client.get(
                "/orders.json",
                headers={"X-Shopify-Access-Token": self._access_token},
                params={
                    "status": "any",  # deliberately includes cancelled orders - see module docstring
                    "created_at_min": created_at_min,
                    "created_at_max": created_at_max,
                    "limit": 250,
                },
            )

        if response.status_code == 401:
            raise ShopifyAuthError(f"Shopify auth failed: {response.text[:300]}")
        if response.status_code == 429:
            raise ShopifyRateLimitError("Shopify rate limit exceeded")
        if response.status_code >= 400:
            raise ShopifyApiError(f"Shopify API returned {response.status_code}: {response.text[:300]}")

        return response.json().get("orders", [])
