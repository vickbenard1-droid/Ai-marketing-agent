"""
Integration tests for the organizations endpoints, including a tenant
isolation check: a user must not be able to see another org's data.
"""
from app.tests.conftest import unique_email


def _register_and_login(client):
    email = unique_email()
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "supersecret123",
            "full_name": "Test User",
            "organization_name": f"Org for {email}",
        },
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_list_organizations_includes_auto_created_personal_org(client, seeded_roles):
    headers = _register_and_login(client)
    resp = client.get("/api/v1/organizations", headers=headers)
    assert resp.status_code == 200
    orgs = resp.json()
    assert len(orgs) == 1
    assert orgs[0]["plan_type"] == "free"


def test_create_additional_organization(client, seeded_roles):
    headers = _register_and_login(client)
    resp = client.post(
        "/api/v1/organizations", json={"name": "Second Org", "is_agency": True}, headers=headers
    )
    assert resp.status_code == 201
    assert resp.json()["is_agency"] is True

    list_resp = client.get("/api/v1/organizations", headers=headers)
    assert len(list_resp.json()) == 2


def test_users_only_see_their_own_organizations(client, seeded_roles):
    """Tenant isolation: user A's org list must never include user B's org."""
    headers_a = _register_and_login(client)
    headers_b = _register_and_login(client)

    orgs_a = client.get("/api/v1/organizations", headers=headers_a).json()
    orgs_b = client.get("/api/v1/organizations", headers=headers_b).json()

    ids_a = {o["id"] for o in orgs_a}
    ids_b = {o["id"] for o in orgs_b}
    assert ids_a.isdisjoint(ids_b)


def test_create_organization_requires_auth(client):
    resp = client.post("/api/v1/organizations", json={"name": "No Auth Org"})
    assert resp.status_code == 401
