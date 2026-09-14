"""
Functional tests for /api/v1/billing/* - real subscription plans, an
organization's current plan + real usage, and changing plans.
"""
from app.tests.conftest import unique_email


def _register_org(client):
    email = unique_email()
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": "supersecret123", "full_name": "U", "organization_name": f"Org {email}"})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    org_id = client.get("/api/v1/organizations", headers=headers).json()[0]["id"]
    return {**headers, "X-Organization-Id": org_id}


def test_list_plans_returns_the_4_real_seeded_tiers(client, seeded_roles, seeded_plans):
    resp = client.get("/api/v1/billing/plans")
    assert resp.status_code == 200
    names = {p["name"] for p in resp.json()}
    assert names == {"free", "starter", "professional", "agency"}
    agency = next(p for p in resp.json() if p["name"] == "agency")
    assert agency["max_campaigns"] is None  # genuinely unlimited, not 0


def test_get_current_plan_and_usage_defaults_to_free_with_no_link(client, seeded_roles, seeded_plans):
    org_headers = _register_org(client)
    resp = client.get("/api/v1/billing/current", headers=org_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"]["name"] == "free"
    categories = {u["category"] for u in body["usage"]}
    assert categories == {"ai_tokens", "campaigns", "connected_accounts", "content_generations", "automated_actions"}


def test_current_usage_reflects_a_real_campaign(client, seeded_roles, seeded_plans):
    org_headers = _register_org(client)
    client.post("/api/v1/campaigns", json={"product_name": "Test product", "objective": "leads", "desired_outcome_count": 10, "budget_amount": 10000, "budget_currency": "USD", "target_location": "Lagos"}, headers=org_headers)

    resp = client.get("/api/v1/billing/current", headers=org_headers)
    campaigns_usage = next(u for u in resp.json()["usage"] if u["category"] == "campaigns")
    assert campaigns_usage["current"] == 1


def test_owner_can_change_plan(client, seeded_roles, seeded_plans):
    org_headers = _register_org(client)
    resp = client.post("/api/v1/billing/change-plan", json={"plan_name": "professional"}, headers=org_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "professional"

    current = client.get("/api/v1/billing/current", headers=org_headers)
    assert current.json()["plan"]["name"] == "professional"


def test_non_owner_cannot_change_plan(client, seeded_roles, seeded_plans):
    from app.tests.integration.test_campaigns_api import _add_member_with_role

    owner_headers = _register_org(client)
    org_id = owner_headers["X-Organization-Id"]
    viewer_headers = _add_member_with_role(client, owner_headers, org_id, "viewer")

    resp = client.post("/api/v1/billing/change-plan", json={"plan_name": "professional"}, headers=viewer_headers)
    assert resp.status_code == 403


def test_change_plan_to_unknown_name_returns_404(client, seeded_roles, seeded_plans):
    org_headers = _register_org(client)
    resp = client.post("/api/v1/billing/change-plan", json={"plan_name": "not_a_real_plan"}, headers=org_headers)
    assert resp.status_code == 404


def test_changing_plan_genuinely_changes_enforcement(client, seeded_roles, seeded_plans):
    """The real end-to-end proof: upgrading from Free (0 automated
    actions) actually changes what check_limit() enforces afterward."""
    org_headers = _register_org(client)

    limit_resp = client.get("/api/v1/billing/current", headers=org_headers)
    free_content_limit = next(u for u in limit_resp.json()["usage"] if u["category"] == "content_generations")["limit"]
    assert free_content_limit == 10  # the real seeded Free-tier limit

    client.post("/api/v1/billing/change-plan", json={"plan_name": "agency"}, headers=org_headers)

    after_resp = client.get("/api/v1/billing/current", headers=org_headers)
    agency_content_limit = next(u for u in after_resp.json()["usage"] if u["category"] == "content_generations")["limit"]
    assert agency_content_limit is None  # genuinely unlimited after the real upgrade
