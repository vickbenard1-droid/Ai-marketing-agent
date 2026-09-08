"""
Functional tests for /api/v1/business-profile/* - the Week 5 brand
voice settings surface, genuinely zero coverage before now.
"""
from app.tests.conftest import unique_email


def _register_org(client):
    email = unique_email()
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": "supersecret123", "full_name": "U", "organization_name": f"Org {email}"})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    org_id = client.get("/api/v1/organizations", headers=headers).json()[0]["id"]
    return {**headers, "X-Organization-Id": org_id}


def test_get_brand_voice_creates_a_default_profile_on_first_call(client, seeded_roles):
    org_headers = _register_org(client)
    resp = client.get("/api/v1/business-profile/brand-voice", headers=org_headers)
    assert resp.status_code == 200
    assert "brand_voice" in resp.json()


def test_set_brand_voice_to_a_preset(client, seeded_roles):
    org_headers = _register_org(client)
    resp = client.put("/api/v1/business-profile/brand-voice", json={"brand_voice": "professional"}, headers=org_headers)
    assert resp.status_code == 200
    assert resp.json()["brand_voice"] == "professional"


def test_set_brand_voice_to_custom_with_text(client, seeded_roles):
    org_headers = _register_org(client)
    resp = client.put("/api/v1/business-profile/brand-voice", json={"brand_voice": "custom", "brand_voice_custom": "Warm, a little cheeky, never corporate-sounding"}, headers=org_headers)
    assert resp.status_code == 200
    assert resp.json()["brand_voice"] == "custom"
    assert resp.json()["brand_voice_custom"] == "Warm, a little cheeky, never corporate-sounding"


def test_brand_voice_persists_across_requests(client, seeded_roles):
    org_headers = _register_org(client)
    client.put("/api/v1/business-profile/brand-voice", json={"brand_voice": "friendly"}, headers=org_headers)
    resp = client.get("/api/v1/business-profile/brand-voice", headers=org_headers)
    assert resp.json()["brand_voice"] == "friendly"


def test_brand_voice_isolated_across_organizations(client, seeded_roles):
    org_a_headers = _register_org(client)
    org_b_headers = _register_org(client)

    client.put("/api/v1/business-profile/brand-voice", json={"brand_voice": "custom", "brand_voice_custom": "Org A's private voice description"}, headers=org_a_headers)

    org_b_profile = client.get("/api/v1/business-profile/brand-voice", headers=org_b_headers)
    assert org_b_profile.json().get("brand_voice_custom") != "Org A's private voice description"
