from app.tests.conftest import unique_email


def _register_and_login(client):
    email = unique_email()
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "supersecret123",
            "full_name": "Test User",
            "organization_name": "Test Org",
        },
    )
    body = resp.json()
    return {"Authorization": f"Bearer {body['access_token']}"}


def _org_headers(client, headers):
    orgs = client.get("/api/v1/organizations", headers=headers).json()
    org_id = orgs[0]["id"]
    return {**headers, "X-Organization-Id": org_id}


def test_get_onboarding_state_creates_profile_on_first_access(client, seeded_roles):
    headers = _org_headers(client, _register_and_login(client))
    resp = client.get("/api/v1/onboarding", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["onboarding_current_step"] == 1
    assert body["onboarding_completed_at"] is None


def test_onboarding_requires_org_header(client, seeded_roles):
    headers = _register_and_login(client)
    resp = client.get("/api/v1/onboarding", headers=headers)
    assert resp.status_code == 422  # missing required X-Organization-Id header


def test_step_2_website_saves_and_advances_step(client, seeded_roles):
    headers = _org_headers(client, _register_and_login(client))
    resp = client.put(
        "/api/v1/onboarding/step-2-website", json={"website_url": "https://acme.example.com"}, headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["website_url"] == "https://acme.example.com"
    assert body["onboarding_current_step"] == 2


def test_step_number_never_regresses(client, seeded_roles):
    headers = _org_headers(client, _register_and_login(client))
    client.put("/api/v1/onboarding/step-4-country", json={"country": "US"}, headers=headers)
    # Revisit an earlier step (e.g. browser back button) — current_step
    # should stay at 4, not drop to 3.
    resp = client.put("/api/v1/onboarding/step-3-industry", json={"industry": "Retail"}, headers=headers)
    assert resp.json()["onboarding_current_step"] == 4


def test_full_onboarding_flow_then_complete(client, seeded_roles):
    headers = _org_headers(client, _register_and_login(client))

    client.put("/api/v1/onboarding/step-2-website", json={"website_url": "https://acme.example.com"}, headers=headers)
    client.put("/api/v1/onboarding/step-3-industry", json={"industry": "Retail"}, headers=headers)
    client.put("/api/v1/onboarding/step-4-country", json={"country": "US"}, headers=headers)
    client.put(
        "/api/v1/onboarding/step-5-products-services",
        json={"products_services": "Handmade candles"},
        headers=headers,
    )
    client.put(
        "/api/v1/onboarding/step-6-target-customers",
        json={"target_customers": "Home decor shoppers aged 25-45"},
        headers=headers,
    )
    client.put("/api/v1/onboarding/step-7-marketing-goal", json={"marketing_goal": "sales"}, headers=headers)
    client.put(
        "/api/v1/onboarding/step-8-budget",
        json={"monthly_ad_budget": 5000, "budget_currency": "USD"},
        headers=headers,
    )
    client.put(
        "/api/v1/onboarding/step-9-social-platforms",
        json={"social_platforms": ["instagram", "tiktok"]},
        headers=headers,
    )
    step10 = client.put(
        "/api/v1/onboarding/step-10-advertising-platforms",
        json={"advertising_platforms": ["meta_ads", "google_ads"]},
        headers=headers,
    )
    assert step10.status_code == 200
    assert step10.json()["onboarding_current_step"] == 10

    complete_resp = client.post("/api/v1/onboarding/complete", headers=headers)
    assert complete_resp.status_code == 200
    body = complete_resp.json()
    assert body["onboarding_completed_at"] is not None
    assert body["social_platforms"] == ["instagram", "tiktok"]
    assert body["advertising_platforms"] == ["meta_ads", "google_ads"]


def test_business_name_step_1_updates_organization_name(client, seeded_roles):
    headers = _org_headers(client, _register_and_login(client))
    resp = client.patch("/api/v1/organizations/current", json={"name": "Renamed Business"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed Business"

    orgs = client.get("/api/v1/organizations", headers=headers).json()
    assert orgs[0]["name"] == "Renamed Business"
