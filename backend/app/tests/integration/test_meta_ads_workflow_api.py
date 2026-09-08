"""
Functional tests for /api/v1/meta-ads/* - the Week 7 Meta Ads
integration's core request/approve/review workflow. Complements
test_meta_ads_isolation_api.py (which covers cross-tenant isolation
specifically for the spend-limit endpoints) with the actual day-to-day
business feature: requesting a budget/status change, listing/reviewing
the resulting approval request, and campaign insight retrieval. Does
NOT cover the final execute step, since that makes a real outbound Meta
API call and requires a mocked HTTP transport - see
app.meta_ads.execution_service's own module-level tests (unit-tested
separately) for that.
"""
import json
import uuid

from app.core.security import encrypt_secret
from app.models.connected_account import ConnectedAccount, ConnectionStatus, PlatformType
from app.models.meta_ad_account import MetaAdAccount
from app.models.meta_campaign import MetaCampaign, MetaCampaignObjective, MetaCampaignStatus
from app.tests.conftest import unique_email


def _register_org_with_campaign(client, db_session, *, daily_budget_cents=2000):
    email = unique_email()
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": "supersecret123", "full_name": "U", "organization_name": f"Org {email}"})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    org_id = client.get("/api/v1/organizations", headers=headers).json()[0]["id"]
    org_headers = {**headers, "X-Organization-Id": org_id}
    project_id = client.post("/api/v1/projects", json={"name": "Default"}, headers=org_headers).json()["id"]

    creds = encrypt_secret(json.dumps({"access_token": "tok"}))
    connected = ConnectedAccount(organization_id=uuid.UUID(org_id), project_id=uuid.UUID(project_id), platform=PlatformType.META_ADS, status=ConnectionStatus.CONNECTED, encrypted_credentials=creds)
    db_session.add(connected)
    db_session.flush()
    ad_account = MetaAdAccount(organization_id=uuid.UUID(org_id), connected_account_id=connected.id, external_ad_account_id=f"act_{email}", name="Ads", currency="USD", timezone_name="UTC")
    db_session.add(ad_account)
    db_session.flush()
    campaign = MetaCampaign(organization_id=uuid.UUID(org_id), meta_ad_account_id=ad_account.id, name="Test Campaign", objective=MetaCampaignObjective.OUTCOME_SALES, external_campaign_id=f"c_{email}", status=MetaCampaignStatus.PAUSED, daily_budget_cents=daily_budget_cents)
    db_session.add(campaign)
    db_session.commit()
    return org_headers, str(campaign.id)


def test_connect_ad_account_and_list(client, seeded_roles, db_session):
    org_headers, _ = _register_org_with_campaign(client, db_session)
    resp = client.get("/api/v1/meta-ads/ad-accounts", headers=org_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_list_meta_campaigns(client, seeded_roles, db_session):
    org_headers, campaign_id = _register_org_with_campaign(client, db_session)
    resp = client.get("/api/v1/meta-ads/meta-campaigns", headers=org_headers)
    assert resp.status_code == 200
    assert resp.json()[0]["id"] == campaign_id


def test_request_budget_change_creates_pending_approval(client, seeded_roles, db_session):
    org_headers, campaign_id = _register_org_with_campaign(client, db_session)
    resp = client.post(f"/api/v1/meta-ads/meta-campaigns/{campaign_id}/request-budget-change", json={"new_daily_budget_cents": 3000}, headers=org_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"
    assert resp.json()["action_type"] == "campaign_budget_change"

    # Confirm no real budget change occurred yet - a request creates a
    # PENDING approval only, never touches the campaign directly.
    campaigns = client.get("/api/v1/meta-ads/meta-campaigns", headers=org_headers).json()
    assert campaigns[0]["daily_budget_cents"] == 2000


def test_request_status_change_creates_pending_approval(client, seeded_roles, db_session):
    org_headers, campaign_id = _register_org_with_campaign(client, db_session)
    resp = client.post(f"/api/v1/meta-ads/meta-campaigns/{campaign_id}/request-status-change", json={"new_status": "ACTIVE"}, headers=org_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


def test_list_and_review_approval_request(client, seeded_roles, db_session):
    org_headers, campaign_id = _register_org_with_campaign(client, db_session)
    create_resp = client.post(f"/api/v1/meta-ads/meta-campaigns/{campaign_id}/request-budget-change", json={"new_daily_budget_cents": 3000}, headers=org_headers)
    approval_id = create_resp.json()["id"]

    list_resp = client.get("/api/v1/meta-ads/approval-requests", headers=org_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    reject_resp = client.post(f"/api/v1/meta-ads/approval-requests/{approval_id}/review", json={"approve": False, "review_notes": "Not now"}, headers=org_headers)
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "rejected"


def test_campaign_insights_empty_when_no_data_yet(client, seeded_roles, db_session):
    org_headers, campaign_id = _register_org_with_campaign(client, db_session)
    resp = client.get(f"/api/v1/meta-ads/meta-campaigns/{campaign_id}/insights", headers=org_headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_meta_campaigns_isolated_across_organizations(client, seeded_roles, db_session):
    org_a_headers, campaign_id_a = _register_org_with_campaign(client, db_session)
    org_b_headers, _ = _register_org_with_campaign(client, db_session)

    exploit_resp = client.get(f"/api/v1/meta-ads/meta-campaigns/{campaign_id_a}/insights", headers=org_b_headers)
    assert exploit_resp.status_code == 404

    org_b_campaigns = client.get("/api/v1/meta-ads/meta-campaigns", headers=org_b_headers).json()
    assert campaign_id_a not in [c["id"] for c in org_b_campaigns]
