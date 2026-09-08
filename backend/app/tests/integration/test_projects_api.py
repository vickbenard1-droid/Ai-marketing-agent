"""
Functional tests for /api/v1/projects/* - genuinely zero coverage
existed for this file before now. Every other test file only ever
calls POST /projects as setup scaffolding for its own tests; nothing
exercised GET/PATCH/DELETE at all.
"""
from app.tests.conftest import unique_email


def _register_org(client):
    email = unique_email()
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": "supersecret123", "full_name": "U", "organization_name": f"Org {email}"})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    org_id = client.get("/api/v1/organizations", headers=headers).json()[0]["id"]
    return {**headers, "X-Organization-Id": org_id}


def test_create_and_list_projects(client, seeded_roles):
    org_headers = _register_org(client)
    create_resp = client.post("/api/v1/projects", json={"name": "My Store"}, headers=org_headers)
    assert create_resp.status_code == 201
    assert create_resp.json()["name"] == "My Store"

    list_resp = client.get("/api/v1/projects", headers=org_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


def test_get_single_project(client, seeded_roles):
    org_headers = _register_org(client)
    project = client.post("/api/v1/projects", json={"name": "My Store"}, headers=org_headers).json()
    resp = client.get(f"/api/v1/projects/{project['id']}", headers=org_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == project["id"]


def test_update_project(client, seeded_roles):
    org_headers = _register_org(client)
    project = client.post("/api/v1/projects", json={"name": "My Store"}, headers=org_headers).json()
    update_resp = client.patch(f"/api/v1/projects/{project['id']}", json={"name": "Renamed Store", "industry": "Retail"}, headers=org_headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Renamed Store"
    assert update_resp.json()["industry"] == "Retail"


def test_delete_project(client, seeded_roles):
    org_headers = _register_org(client)
    project = client.post("/api/v1/projects", json={"name": "Temp Project"}, headers=org_headers).json()
    delete_resp = client.delete(f"/api/v1/projects/{project['id']}", headers=org_headers)
    assert delete_resp.status_code == 200

    get_resp = client.get(f"/api/v1/projects/{project['id']}", headers=org_headers)
    assert get_resp.status_code == 404


def test_get_nonexistent_project_returns_404(client, seeded_roles):
    import uuid
    org_headers = _register_org(client)
    resp = client.get(f"/api/v1/projects/{uuid.uuid4()}", headers=org_headers)
    assert resp.status_code == 404


def test_projects_isolated_across_organizations(client, seeded_roles):
    org_a_headers = _register_org(client)
    org_b_headers = _register_org(client)

    project = client.post("/api/v1/projects", json={"name": "Org A's private project"}, headers=org_a_headers).json()

    exploit_get = client.get(f"/api/v1/projects/{project['id']}", headers=org_b_headers)
    assert exploit_get.status_code == 404

    exploit_update = client.patch(f"/api/v1/projects/{project['id']}", json={"name": "Hacked"}, headers=org_b_headers)
    assert exploit_update.status_code == 404

    exploit_delete = client.delete(f"/api/v1/projects/{project['id']}", headers=org_b_headers)
    assert exploit_delete.status_code == 404

    org_b_list = client.get("/api/v1/projects", headers=org_b_headers).json()
    assert len(org_b_list) == 0
