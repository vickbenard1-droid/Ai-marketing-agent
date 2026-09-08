"""
Cross-tenant isolation regression tests for /api/v1/meta-ads/*.

This file exists specifically because a real cross-tenant data leak was
found and fixed during the Week 12 security audit: GET
/meta-ads/ad-accounts/{ad_account_id}/spend-limit fetched the spend
limit by ad_account_id alone, with no check that the ad account
actually belonged to the caller's organization - any authenticated user
in ANY organization could read another organization's real daily spend
limit and emergency-stop status by passing its ad_account_id.

These tests exist to make sure that specific bug (and its shape - a
resource fetched by a path-supplied foreign key with no owning-org
check) can never silently come back.
"""
import json
import uuid

from app.core.security import encrypt_secret
from app.models.connected_account import ConnectedAccount, ConnectionStatus, PlatformType
from app.tests.conftest import unique_email


def _register_org_with_ad_account(client, db_session, *, daily_spend_limit_cents: int):
    email = unique_email()
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "supersecret123", "full_name": "Test User", "organization_name": f"Org {email}"},
    )
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    org_id = client.get("/api/v1/organizations", headers=headers).json()[0]["id"]
    org_headers = {**headers, "X-Organization-Id": org_id}
    project_id = client.post("/api/v1/projects", json={"name": "Default"}, headers=org_headers).json()["id"]

    creds = encrypt_secret(json.dumps({"access_token": "tok"}))
    connected = ConnectedAccount(
        organization_id=uuid.UUID(org_id), project_id=uuid.UUID(project_id), platform=PlatformType.META_ADS,
        status=ConnectionStatus.CONNECTED, encrypted_credentials=creds,
    )
    db_session.add(connected)
    db_session.commit()

    ad_account_resp = client.post(
        "/api/v1/meta-ads/ad-accounts",
        json={"connected_account_id": str(connected.id), "external_ad_account_id": f"act_{unique_email()}", "name": "Secret Ads", "currency": "USD", "timezone_name": "UTC"},
        headers=org_headers,
    )
    ad_account_id = ad_account_resp.json()["id"]
    client.put(f"/api/v1/meta-ads/ad-accounts/{ad_account_id}/spend-limit", json={"daily_spend_limit_cents": daily_spend_limit_cents}, headers=org_headers)
    return org_headers, ad_account_id


def test_org_can_read_its_own_spend_limit(client, seeded_roles, db_session):
    org_headers, ad_account_id = _register_org_with_ad_account(client, db_session, daily_spend_limit_cents=500000)
    resp = client.get(f"/api/v1/meta-ads/ad-accounts/{ad_account_id}/spend-limit", headers=org_headers)
    assert resp.status_code == 200
    assert resp.json()["daily_spend_limit_cents"] == 500000


def test_org_cannot_read_another_orgs_spend_limit(client, seeded_roles, db_session):
    """The actual regression test for the fixed vulnerability."""
    _, victim_ad_account_id = _register_org_with_ad_account(client, db_session, daily_spend_limit_cents=999999)
    attacker_headers, _ = _register_org_with_ad_account(client, db_session, daily_spend_limit_cents=100)

    exploit_resp = client.get(f"/api/v1/meta-ads/ad-accounts/{victim_ad_account_id}/spend-limit", headers=attacker_headers)
    assert exploit_resp.status_code == 404
    assert "999999" not in exploit_resp.text


def test_org_cannot_set_another_orgs_spend_limit(client, seeded_roles, db_session):
    """The PUT endpoint's existing org-check, kept honest by a real test."""
    _, victim_ad_account_id = _register_org_with_ad_account(client, db_session, daily_spend_limit_cents=999999)
    attacker_headers, _ = _register_org_with_ad_account(client, db_session, daily_spend_limit_cents=100)

    exploit_resp = client.put(f"/api/v1/meta-ads/ad-accounts/{victim_ad_account_id}/spend-limit", json={"daily_spend_limit_cents": 1}, headers=attacker_headers)
    assert exploit_resp.status_code == 404


def test_org_cannot_force_emergency_stop_on_another_orgs_ad_account(client, seeded_roles, db_session):
    """Regression test for a second, higher-severity vulnerability found in the
    same audit pass: set_emergency_stop could mutate ANY organization's real
    ad-spend emergency-stop state (force-stop or force-resume real advertising)
    with no ownership check on the ad_account_id."""
    victim_headers, victim_ad_account_id = _register_org_with_ad_account(client, db_session, daily_spend_limit_cents=50000)
    attacker_headers, _ = _register_org_with_ad_account(client, db_session, daily_spend_limit_cents=100)

    exploit_resp = client.post(f"/api/v1/meta-ads/ad-accounts/{victim_ad_account_id}/emergency-stop", json={"stopped": True, "reason": "malicious"}, headers=attacker_headers)
    assert exploit_resp.status_code == 404

    victim_check = client.get(f"/api/v1/meta-ads/ad-accounts/{victim_ad_account_id}/spend-limit", headers=victim_headers)
    assert victim_check.json()["is_emergency_stopped"] is False

    legit_resp = client.post(f"/api/v1/meta-ads/ad-accounts/{victim_ad_account_id}/emergency-stop", json={"stopped": True, "reason": "legit"}, headers=victim_headers)
    assert legit_resp.status_code == 200
    assert legit_resp.json()["is_emergency_stopped"] is True
