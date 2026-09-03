"""
Meta Marketing API client.

transport is None in production (real network); tests inject an
httpx.MockTransport here instead of patching httpx.Client globally -
patching httpx.Client.request/post globally would ALSO intercept
FastAPI's own TestClient's requests into this app, since TestClient is
itself httpx-based. This was a real bug caught and fixed during the
original build of this module; the constructor parameter exists
specifically to make that mistake structurally impossible to repeat.

Every method maps a raw httpx response to one of the 5
app.meta_ads.errors categories based on Meta's own error response
shape, so callers can react differently to genuinely different failure
modes rather than catching one generic exception.
"""
from typing import Optional

import httpx

from app.meta_ads.errors import MetaApiError, MetaAuthError, MetaPermissionError, MetaRateLimitError, MetaValidationError

GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def _raise_for_meta_error(response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    try:
        body = response.json()
    except ValueError:
        raise MetaApiError(f"Meta API returned {response.status_code} with a non-JSON body: {response.text[:300]}")

    error = body.get("error", {})
    error_type = error.get("type", "")
    error_code = error.get("code")
    message = error.get("message", "Unknown Meta API error")

    if error_type == "OAuthException" or error_code in (190, 102):
        raise MetaAuthError(message)
    if error_code in (200, 10) or "permission" in message.lower():
        raise MetaPermissionError(message)
    if error_code in (4, 17, 32, 613):
        raise MetaRateLimitError(message)
    if error_type == "GraphMethodException" or response.status_code == 400:
        raise MetaValidationError(message)
    raise MetaApiError(f"{message} (type={error_type}, code={error_code})")


class MetaMarketingClient:
    def __init__(self, access_token: str, *, transport: Optional[httpx.BaseTransport] = None):
        self._access_token = access_token
        self._transport = transport

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=GRAPH_API_BASE, timeout=30.0, transport=self._transport)

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        params = dict(params or {})
        params["access_token"] = self._access_token
        with self._client() as client:
            response = client.get(path, params=params)
        _raise_for_meta_error(response)
        return response.json()

    def _post(self, path: str, data: dict) -> dict:
        data = dict(data)
        data["access_token"] = self._access_token
        with self._client() as client:
            response = client.post(path, data=data)
        _raise_for_meta_error(response)
        return response.json()

    def list_ad_accounts(self) -> list:
        result = self._get("/me/adaccounts", params={"fields": "id,name,currency,timezone_name"})
        return result.get("data", [])

    def get_campaign(self, campaign_id: str) -> dict:
        return self._get(
            f"/{campaign_id}", params={"fields": "id,name,objective,status,daily_budget,lifetime_budget"}
        )

    def create_campaign(self, ad_account_id: str, *, name: str, objective: str, status: str = "PAUSED") -> dict:
        return self._post(
            f"/act_{ad_account_id}/campaigns", data={"name": name, "objective": objective, "status": status}
        )

    def update_campaign(self, campaign_id: str, **fields) -> dict:
        return self._post(f"/{campaign_id}", data=fields)

    def get_insights(self, entity_id: str, *, date_start: str, date_stop: str) -> list:
        result = self._get(
            f"/{entity_id}/insights",
            params={
                "fields": "impressions,clicks,spend,reach,actions,action_values",
                "time_range": f'{{"since":"{date_start}","until":"{date_stop}"}}',
                "time_increment": 1,
            },
        )
        return result.get("data", [])
