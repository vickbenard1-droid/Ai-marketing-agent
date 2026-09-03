"""
Google Analytics 4 (GA4) source client.

GA4's Data API returns rows as parallel dimensionValues/metricValues
arrays with NO field names attached to each row - the field names only
appear once, in the request's own dimensions/metrics lists. Correctly
zipping a row's positional array values back to named fields (using the
same dimensions/metrics order the request itself specified) is the
genuinely tricky part of this client; get_traffic_metrics() does that
zip explicitly rather than assuming the response carries its own field
names (it doesn't).
"""
from typing import Optional

import httpx

GA4_API_BASE = "https://analyticsdata.googleapis.com/v1beta"


class GA4ApiError(Exception):
    pass


class GA4AuthError(GA4ApiError):
    pass


class GA4RateLimitError(GA4ApiError):
    pass


class GoogleAnalyticsClient:
    def __init__(self, access_token: str, *, transport: Optional[httpx.BaseTransport] = None):
        self._access_token = access_token
        self._transport = transport

    def get_traffic_metrics(self, property_id: str, *, date_start: str, date_stop: str) -> list:
        dimensions = ["date", "sessionSource", "sessionCampaignName"]
        metrics = ["sessions", "conversions", "totalRevenue"]

        with httpx.Client(base_url=GA4_API_BASE, timeout=30.0, transport=self._transport) as client:
            response = client.post(
                f"/properties/{property_id}:runReport",
                headers={"Authorization": f"Bearer {self._access_token}"},
                json={
                    "dateRanges": [{"startDate": date_start, "endDate": date_stop}],
                    "dimensions": [{"name": d} for d in dimensions],
                    "metrics": [{"name": m} for m in metrics],
                },
            )

        if response.status_code == 401:
            raise GA4AuthError(f"GA4 auth failed: {response.text[:300]}")
        if response.status_code == 429:
            raise GA4RateLimitError("GA4 rate limit exceeded")
        if response.status_code >= 400:
            raise GA4ApiError(f"GA4 API returned {response.status_code}: {response.text[:300]}")

        body = response.json()
        rows = []
        for raw_row in body.get("rows", []):
            dim_values = [d["value"] for d in raw_row.get("dimensionValues", [])]
            metric_values = [m["value"] for m in raw_row.get("metricValues", [])]
            named_row = dict(zip(dimensions, dim_values))
            named_row.update(dict(zip(metrics, metric_values)))
            rows.append(named_row)
        return rows
