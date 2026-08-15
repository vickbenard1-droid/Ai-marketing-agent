"""
Integration tests for /api/v1/oauth/* and /api/v1/connected-accounts/*.

The callback endpoint is deliberately tested WITHOUT any auth headers -
that's the whole point of its design (see
app/api/v1/endpoints/connected_accounts.py's module docstring). These
tests confirm state-based "auth" actually works end to end through the
real FastAPI app, not just at the service layer.
"""
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import httpx

from app.core.config import settings
from app.tests.conftest import unique_email


def _register_and_org_headers(client):
    email = unique_email()
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "supersecret123",
            "full_name": "Test User",
            "organization_name": "Acme Candles",
        },
    )
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    orgs = client.get("/api/v1/organizations", headers=headers).json()
    return {**headers, "X-Organization-Id": orgs[0]["id"]}


def _add_member_with_role(client, owner_headers, org_id, role_name):
    email = unique_email()
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "supersecret123",
            "full_name": role_name.title(),
            "organization_name": f"{role_name} org",
        },
    )
    token = resp.json()["access_token"]
    client.post(
        "/api/v1/organizations/current/members",
        json={"email": email, "role_name": role_name},
        headers=owner_headers,
    )
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


def _create_project(client, headers, name="Default"):
    return client.post("/api/v1/projects", json={"name": name}, headers=headers).json()


def _mock_post(self, url, **kwargs):
    return httpx.Response(
        200,
        json={
            "access_token": "real-access-tok",
            "refresh_token": "real-refresh-tok",
            "expires_in": 3600,
            "scope": "w_organization_social",
        },
    )


def test_list_platforms_no_auth_required(client, seeded_roles, monkeypatch):
    monkeypatch.setattr(settings, "LINKEDIN_CLIENT_ID", "test-id")
    monkeypatch.setattr(settings, "LINKEDIN_CLIENT_SECRET", "test-secret")

    resp = client.get("/api/v1/oauth/platforms")
    assert resp.status_code == 200
    platforms = {p["platform"]: p["configured"] for p in resp.json()}
    assert platforms["linkedin_page"] is True
    assert platforms["x_account"] is False  # not configured in this test


def test_start_connect_requires_can_manage_integrations(client, seeded_roles, monkeypatch):
    monkeypatch.setattr(settings, "LINKEDIN_CLIENT_ID", "test-id")
    monkeypatch.setattr(settings, "LINKEDIN_CLIENT_SECRET", "test-secret")
    owner_headers = _register_and_org_headers(client)
    org_id = owner_headers["X-Organization-Id"]
    project = _create_project(client, owner_headers)

    analyst_headers = _add_member_with_role(client, owner_headers, org_id, "analyst")
    resp = client.post(
        "/api/v1/oauth/linkedin_page/connect",
        json={"project_id": project["id"]},
        headers=analyst_headers,
    )
    assert resp.status_code == 403


def test_start_connect_returns_authorize_url(client, seeded_roles, monkeypatch):
    monkeypatch.setattr(settings, "LINKEDIN_CLIENT_ID", "test-id")
    monkeypatch.setattr(settings, "LINKEDIN_CLIENT_SECRET", "test-secret")
    headers = _register_and_org_headers(client)
    project = _create_project(client, headers)

    resp = client.post(
        "/api/v1/oauth/linkedin_page/connect", json={"project_id": project["id"]}, headers=headers
    )
    assert resp.status_code == 200
    assert "linkedin.com" in resp.json()["authorize_url"]
    assert "state=" in resp.json()["authorize_url"]


def test_start_connect_unconfigured_platform_fails_clearly(client, seeded_roles):
    headers = _register_and_org_headers(client)
    project = _create_project(client, headers)

    resp = client.post("/api/v1/oauth/x_account/connect", json={"project_id": project["id"]}, headers=headers)
    assert resp.status_code == 400
    assert "not configured" in resp.json()["detail"].lower()


def test_full_connect_flow_via_real_http_including_unauthenticated_callback(
    client, seeded_roles, db_session, monkeypatch
):
    """
    The core test: start a connect flow as an authenticated user, then
    hit the callback with ZERO auth headers (exactly as a real browser
    redirect from LinkedIn would), and confirm it still works correctly
    because the state parameter itself carries the authorization.
    """
    monkeypatch.setattr(settings, "LINKEDIN_CLIENT_ID", "test-id")
    monkeypatch.setattr(settings, "LINKEDIN_CLIENT_SECRET", "test-secret")
    headers = _register_and_org_headers(client)
    project = _create_project(client, headers)

    start_resp = client.post(
        "/api/v1/oauth/linkedin_page/connect", json={"project_id": project["id"]}, headers=headers
    )
    authorize_url = start_resp.json()["authorize_url"]
    state_value = parse_qs(urlparse(authorize_url).query)["state"][0]

    with patch("httpx.Client.post", _mock_post):
        callback_resp = client.get(
            "/api/v1/oauth/linkedin_page/callback",
            params={"code": "authcode123", "state": state_value},
            follow_redirects=False,
            # Deliberately NO headers at all.
        )

    assert callback_resp.status_code in (302, 307)
    assert "connected=linkedin_page" in callback_resp.headers["location"]

    list_resp = client.get("/api/v1/connected-accounts", headers=headers)
    assert list_resp.status_code == 200
    accounts = list_resp.json()
    assert len(accounts) == 1
    assert accounts[0]["platform"] == "linkedin_page"
    assert accounts[0]["status"] == "connected"

    body_str = str(accounts[0])
    assert "real-access-tok" not in body_str
    assert "real-refresh-tok" not in body_str
    assert "encrypted_credentials" not in accounts[0]
    assert "access_token" not in accounts[0]


def test_callback_with_invalid_state_is_rejected(client, seeded_roles, monkeypatch):
    monkeypatch.setattr(settings, "LINKEDIN_CLIENT_ID", "test-id")
    monkeypatch.setattr(settings, "LINKEDIN_CLIENT_SECRET", "test-secret")

    resp = client.get(
        "/api/v1/oauth/linkedin_page/callback",
        params={"code": "whatever", "state": "totally-made-up-state-value"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 307)
    assert "error=" in resp.headers["location"]


def test_callback_state_cannot_be_replayed(client, seeded_roles, monkeypatch):
    monkeypatch.setattr(settings, "LINKEDIN_CLIENT_ID", "test-id")
    monkeypatch.setattr(settings, "LINKEDIN_CLIENT_SECRET", "test-secret")
    headers = _register_and_org_headers(client)
    project = _create_project(client, headers)

    start_resp = client.post(
        "/api/v1/oauth/linkedin_page/connect", json={"project_id": project["id"]}, headers=headers
    )
    state_value = parse_qs(urlparse(start_resp.json()["authorize_url"]).query)["state"][0]

    with patch("httpx.Client.post", _mock_post):
        first = client.get(
            "/api/v1/oauth/linkedin_page/callback",
            params={"code": "code1", "state": state_value},
            follow_redirects=False,
        )
        assert "connected=" in first.headers["location"]

        second = client.get(
            "/api/v1/oauth/linkedin_page/callback",
            params={"code": "code2-replay-attempt", "state": state_value},
            follow_redirects=False,
        )
    assert "error=" in second.headers["location"]


def test_disconnect_account(client, seeded_roles, monkeypatch):
    monkeypatch.setattr(settings, "LINKEDIN_CLIENT_ID", "test-id")
    monkeypatch.setattr(settings, "LINKEDIN_CLIENT_SECRET", "test-secret")
    headers = _register_and_org_headers(client)
    project = _create_project(client, headers)

    start_resp = client.post(
        "/api/v1/oauth/linkedin_page/connect", json={"project_id": project["id"]}, headers=headers
    )
    state_value = parse_qs(urlparse(start_resp.json()["authorize_url"]).query)["state"][0]

    with patch("httpx.Client.post", _mock_post):
        client.get(
            "/api/v1/oauth/linkedin_page/callback",
            params={"code": "code1", "state": state_value},
            follow_redirects=False,
        )

    account_id = client.get("/api/v1/connected-accounts", headers=headers).json()[0]["id"]

    disconnect_resp = client.post(f"/api/v1/connected-accounts/{account_id}/disconnect", headers=headers)
    assert disconnect_resp.status_code == 200
    assert disconnect_resp.json()["status"] == "disconnected"

    list_resp = client.get("/api/v1/connected-accounts", headers=headers)
    assert len(list_resp.json()) == 0


def test_connected_accounts_isolated_across_organizations(client, seeded_roles, monkeypatch):
    monkeypatch.setattr(settings, "LINKEDIN_CLIENT_ID", "test-id")
    monkeypatch.setattr(settings, "LINKEDIN_CLIENT_SECRET", "test-secret")
    org_a_headers = _register_and_org_headers(client)
    org_b_headers = _register_and_org_headers(client)
    project_a = _create_project(client, org_a_headers)

    start_resp = client.post(
        "/api/v1/oauth/linkedin_page/connect", json={"project_id": project_a["id"]}, headers=org_a_headers
    )
    state_value = parse_qs(urlparse(start_resp.json()["authorize_url"]).query)["state"][0]

    with patch("httpx.Client.post", _mock_post):
        client.get(
            "/api/v1/oauth/linkedin_page/callback",
            params={"code": "code1", "state": state_value},
            follow_redirects=False,
        )

    org_b_list = client.get("/api/v1/connected-accounts", headers=org_b_headers).json()
    assert len(org_b_list) == 0
