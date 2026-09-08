"""
Functional tests for /api/v1/analytics/* - the Week 8 unified analytics
dashboard, conversion type management, and tracking key management.
"""
import datetime

from app.tests.conftest import unique_email


def _register_org(client):
    email = unique_email()
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": "supersecret123", "full_name": "U", "organization_name": f"Org {email}"})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    org_id = client.get("/api/v1/organizations", headers=headers).json()[0]["id"]
    return {**headers, "X-Organization-Id": org_id}


def test_dashboard_returns_honest_nulls_with_no_data(client, seeded_roles):
    org_headers = _register_org(client)
    today = datetime.date.today().isoformat()
    resp = client.get(f"/api/v1/analytics/dashboard?date_start={today}&date_stop={today}", headers=org_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["raw"]["impressions"] == 0
    assert body["derived"]["ctr"] is None  # unmeasured, not fabricated zero


def test_conversion_types_seeds_defaults_on_first_call(client, seeded_roles):
    org_headers = _register_org(client)
    resp = client.get("/api/v1/analytics/conversion-types", headers=org_headers)
    assert resp.status_code == 200
    assert len(resp.json()) > 0  # real default types seeded automatically


def test_create_conversion_type(client, seeded_roles):
    org_headers = _register_org(client)
    resp = client.post("/api/v1/analytics/conversion-types", json={"name": "Newsletter signup", "category": "lead", "counts_as_revenue": False}, headers=org_headers)
    assert resp.status_code == 201
    assert resp.json()["name"] == "Newsletter signup"
    assert resp.json()["counts_as_revenue"] is False


def test_get_and_regenerate_tracking_key(client, seeded_roles):
    org_headers = _register_org(client)
    first_resp = client.get("/api/v1/analytics/tracking-key", headers=org_headers)
    assert first_resp.status_code == 200
    first_key = first_resp.json()["key"]

    same_key_resp = client.get("/api/v1/analytics/tracking-key", headers=org_headers)
    assert same_key_resp.json()["key"] == first_key  # idempotent - not regenerated on every GET

    regen_resp = client.post("/api/v1/analytics/tracking-key/regenerate", headers=org_headers)
    assert regen_resp.status_code == 200
    assert regen_resp.json()["key"] != first_key  # genuinely regenerated


def test_analytics_isolated_across_organizations(client, seeded_roles):
    org_a_headers = _register_org(client)
    org_b_headers = _register_org(client)

    key_a = client.get("/api/v1/analytics/tracking-key", headers=org_a_headers).json()["key"]
    key_b = client.get("/api/v1/analytics/tracking-key", headers=org_b_headers).json()["key"]
    assert key_a != key_b

    type_resp = client.post("/api/v1/analytics/conversion-types", json={"name": "Org A's private type", "category": "purchase", "counts_as_revenue": True}, headers=org_a_headers)
    assert type_resp.status_code == 201

    org_b_types = client.get("/api/v1/analytics/conversion-types", headers=org_b_headers).json()
    assert "Org A's private type" not in [t["name"] for t in org_b_types]
