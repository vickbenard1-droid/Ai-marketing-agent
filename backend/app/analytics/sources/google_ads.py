"""
Google Ads source client.

Transport-injectable, same pattern and same reasoning as
app.meta_ads.meta_client.MetaMarketingClient - avoids colliding with
FastAPI's own TestClient in tests.

GAQL (Google Ads Query Language) results arrive via a
searchStream-style paginated response - Google's real API returns
results in multiple chunks for a large query, each chunk itself
containing a "results" array; get_campaign_metrics() flattens every
chunk into one flat list rather than returning the raw chunked shape,
since nothing downstream in this app needs to know about Google's own
internal pagination/batching mechanics.
"""
from typing import Optional

import httpx

GOOGLE_ADS_API_VERSION = "v17"
GOOGLE_ADS_API_BASE = f"https://googleads.googleapis.com/{GOOGLE_ADS_API_VERSION}"


class GoogleAdsApiError(Exception):
    pass


class GoogleAdsAuthError(GoogleAdsApiError):
    pass


class GoogleAdsRateLimitError(GoogleAdsApiError):
    pass


class GoogleAdsClient:
    def __init__(
        self,
        access_token: str,
        *,
        developer_token: str,
        login_customer_id: Optional[str] = None,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self._access_token = access_token
        self._developer_token = developer_token
        self._login_customer_id = login_customer_id
        self._transport = transport

    def _headers(self) -> dict:
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "developer-token": self._developer_token,
        }
        if self._login_customer_id:
            headers["login-customer-id"] = self._login_customer_id
        return headers

    def get_campaign_metrics(self, customer_id: str, *, date_start: str, date_stop: str) -> list:
        query = (
            "SELECT campaign.id, campaign.name, segments.date, "
            "metrics.impressions, metrics.clicks, metrics.cost_micros, "
            "metrics.conversions, metrics.conversions_value "
            f"FROM campaign WHERE segments.date BETWEEN '{date_start}' AND '{date_stop}'"
        )
        with httpx.Client(base_url=GOOGLE_ADS_API_BASE, timeout=30.0, transport=self._transport) as client:
            response = client.post(
                f"/customers/{customer_id}/googleAds:searchStream", headers=self._headers(), json={"query": query}
            )

        if response.status_code == 401:
            raise GoogleAdsAuthError(f"Google Ads auth failed: {response.text[:300]}")
        if response.status_code == 429:
            raise GoogleAdsRateLimitError("Google Ads rate limit exceeded")
        if response.status_code >= 400:
            raise GoogleAdsApiError(f"Google Ads API returned {response.status_code}: {response.text[:300]}")

        chunks = response.json()
        flattened = []
        for chunk in chunks:
            flattened.extend(chunk.get("results", []))
        return flattened
