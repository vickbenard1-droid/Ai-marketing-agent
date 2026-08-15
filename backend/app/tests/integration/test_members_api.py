from app.tests.conftest import unique_email


def _register(client, email=None, password="supersecret123"):
    email = email or unique_email()
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Test User",
            "organization_name": "Test Org",
        },
    )
    body = resp.json()
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    return headers, email


def _org_headers(client, headers):
    orgs = client.get("/api/v1/organizations", headers=headers).json()
    return {**headers, "X-Organization-Id": orgs[0]["id"]}, orgs[0]["id"]


def test_list_roles_returns_all_six(client, seeded_roles):
    headers, _ = _register(client)
    headers, _ = _org_headers(client, headers)
    resp = client.get("/api/v1/roles", headers=headers)
    assert resp.status_code == 200
    names = {r["name"] for r in resp.json()}
    assert names == {"owner", "admin", "manager", "analyst", "content_manager", "viewer"}


def test_owner_can_list_members(client, seeded_roles):
    headers, email = _register(client)
    headers, _ = _org_headers(client, headers)
    resp = client.get("/api/v1/organizations/current/members", headers=headers)
    assert resp.status_code == 200
    members = resp.json()
    assert len(members) == 1
    assert members[0]["email"] == email
    assert members[0]["role"]["name"] == "owner"


def test_owner_can_invite_existing_user(client, seeded_roles):
    owner_headers, _ = _register(client)
    owner_headers, org_id = _org_headers(client, owner_headers)

    # Second user must already have an account (Week 2 scope — see
    # schemas/member.py::InviteMemberRequest docstring).
    invitee_headers, invitee_email = _register(client)

    resp = client.post(
        "/api/v1/organizations/current/members",
        json={"email": invitee_email, "role_name": "manager"},
        headers=owner_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == invitee_email
    assert body["role"]["name"] == "manager"


def test_invite_nonexistent_user_fails(client, seeded_roles):
    owner_headers, _ = _register(client)
    owner_headers, _ = _org_headers(client, owner_headers)
    resp = client.post(
        "/api/v1/organizations/current/members",
        json={"email": "nobody@example.com", "role_name": "manager"},
        headers=owner_headers,
    )
    assert resp.status_code == 400


def test_invite_already_member_fails(client, seeded_roles):
    owner_headers, owner_email = _register(client)
    owner_headers, _ = _org_headers(client, owner_headers)
    # Inviting the owner themselves (already a member of their own org).
    resp = client.post(
        "/api/v1/organizations/current/members",
        json={"email": owner_email, "role_name": "manager"},
        headers=owner_headers,
    )
    assert resp.status_code == 400


def test_viewer_cannot_invite_members(client, seeded_roles):
    """RBAC enforcement: a member with can_manage_members=False must be
    rejected by the server, regardless of what the frontend would show."""
    owner_headers, _ = _register(client)
    owner_headers, org_id = _org_headers(client, owner_headers)

    viewer_headers, viewer_email = _register(client)
    client.post(
        "/api/v1/organizations/current/members",
        json={"email": viewer_email, "role_name": "viewer"},
        headers=owner_headers,
    )

    # Viewer must switch their active org context to the org they were
    # just added to before acting within it.
    viewer_org_headers = {**viewer_headers, "X-Organization-Id": org_id}
    another_invitee_headers, another_email = _register(client)

    resp = client.post(
        "/api/v1/organizations/current/members",
        json={"email": another_email, "role_name": "manager"},
        headers=viewer_org_headers,
    )
    assert resp.status_code == 403


def test_cannot_demote_the_only_owner(client, seeded_roles):
    owner_headers, _ = _register(client)
    owner_headers, org_id = _org_headers(client, owner_headers)

    members = client.get("/api/v1/organizations/current/members", headers=owner_headers).json()
    owner_member_id = members[0]["id"]

    resp = client.patch(
        f"/api/v1/organizations/current/members/{owner_member_id}",
        json={"role_name": "admin"},
        headers=owner_headers,
    )
    assert resp.status_code == 400


def test_cannot_remove_the_only_owner(client, seeded_roles):
    owner_headers, _ = _register(client)
    owner_headers, _ = _org_headers(client, owner_headers)

    members = client.get("/api/v1/organizations/current/members", headers=owner_headers).json()
    owner_member_id = members[0]["id"]

    resp = client.delete(
        f"/api/v1/organizations/current/members/{owner_member_id}", headers=owner_headers
    )
    assert resp.status_code == 400


def test_owner_can_remove_a_non_owner_member(client, seeded_roles):
    owner_headers, _ = _register(client)
    owner_headers, org_id = _org_headers(client, owner_headers)

    invitee_headers, invitee_email = _register(client)
    invite_resp = client.post(
        "/api/v1/organizations/current/members",
        json={"email": invitee_email, "role_name": "manager"},
        headers=owner_headers,
    )
    member_id = invite_resp.json()["id"]

    resp = client.delete(f"/api/v1/organizations/current/members/{member_id}", headers=owner_headers)
    assert resp.status_code == 200

    members = client.get("/api/v1/organizations/current/members", headers=owner_headers).json()
    assert len(members) == 1  # only the owner remains


def test_members_endpoint_isolated_across_organizations(client, seeded_roles):
    """Tenant isolation: org A's member list must never include org B's members."""
    org_a_headers, org_a_email = _register(client)
    org_a_headers, org_a_id = _org_headers(client, org_a_headers)

    org_b_headers, org_b_email = _register(client)
    org_b_headers, org_b_id = _org_headers(client, org_b_headers)

    members_a = client.get("/api/v1/organizations/current/members", headers=org_a_headers).json()
    members_b = client.get("/api/v1/organizations/current/members", headers=org_b_headers).json()

    emails_a = {m["email"] for m in members_a}
    emails_b = {m["email"] for m in members_b}
    assert emails_a.isdisjoint(emails_b)
