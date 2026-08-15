from app.tests.conftest import unique_email


def _org_headers(client):
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


def test_dashboard_summary_empty_state_before_onboarding(client, seeded_roles):
    headers = _org_headers(client)
    resp = client.get("/api/v1/dashboard/summary", headers=headers)
    assert resp.status_code == 200
    body = resp.json()

    assert body["business_name"] == "Acme Candles"
    assert body["marketing_goal"] is None
    assert body["monthly_ad_budget"] is None
    assert body["onboarding_completed"] is False
    assert body["connected_platforms_count"] == 0

    # No fake performance data — everything must be a real zero/None empty
    # state, per the Week 2 spec.
    assert body["campaign_count"] == 0
    assert body["content_count"] == 0
    assert body["leads_count"] == 0
    assert body["sales_count"] == 0
    assert body["total_spend"] == 0.0


def test_dashboard_summary_reflects_onboarding_data(client, seeded_roles):
    headers = _org_headers(client)
    client.put("/api/v1/onboarding/step-7-marketing-goal", json={"marketing_goal": "leads"}, headers=headers)
    client.put(
        "/api/v1/onboarding/step-8-budget",
        json={"monthly_ad_budget": 2500, "budget_currency": "USD"},
        headers=headers,
    )
    client.post("/api/v1/onboarding/complete", headers=headers)

    resp = client.get("/api/v1/dashboard/summary", headers=headers)
    body = resp.json()
    assert body["marketing_goal"] == "leads"
    assert body["monthly_ad_budget"] == 2500
    assert body["onboarding_completed"] is True


def test_dashboard_summary_requires_org_header(client, seeded_roles):
    email = unique_email()
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "supersecret123",
            "full_name": "Test User",
            "organization_name": "Org",
        },
    )
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    dash_resp = client.get("/api/v1/dashboard/summary", headers=headers)
    assert dash_resp.status_code == 422
