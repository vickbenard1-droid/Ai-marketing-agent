"""
Functional tests for /api/v1/optimization/* - the Week 9 autonomous
optimization agent's settings, whitelist, and decision-review workflow.
"""
import json
import uuid

from app.core.security import encrypt_secret
from app.models.connected_account import ConnectedAccount, ConnectionStatus, PlatformType
from app.models.meta_ad_account import MetaAdAccount
from app.models.meta_campaign import MetaCampaign, MetaCampaignObjective, MetaCampaignStatus
from app.models.optimization_decision import DecisionRisk, DecisionStatus, OptimizationActionType, OptimizationDecision
from app.tests.conftest import unique_email


def _register_org_with_campaign(client, db_session):
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
    campaign = MetaCampaign(organization_id=uuid.UUID(org_id), meta_ad_account_id=ad_account.id, name="Test Campaign", objective=MetaCampaignObjective.OUTCOME_SALES, external_campaign_id=f"c_{email}", status=MetaCampaignStatus.ACTIVE, daily_budget_cents=1000)
    db_session.add(campaign)
    db_session.commit()
    return org_headers, str(campaign.id)


def test_get_autonomy_settings_defaults_to_manual(client, seeded_roles, db_session):
    org_headers, campaign_id = _register_org_with_campaign(client, db_session)
    resp = client.get(f"/api/v1/optimization/meta-campaigns/{campaign_id}/autonomy-settings", headers=org_headers)
    assert resp.status_code == 200
    assert resp.json()["autonomy_level"] == "manual"
    assert resp.json()["is_emergency_stopped"] is False


def test_set_autonomy_settings(client, seeded_roles, db_session):
    org_headers, campaign_id = _register_org_with_campaign(client, db_session)
    resp = client.put(
        f"/api/v1/optimization/meta-campaigns/{campaign_id}/autonomy-settings",
        json={"autonomy_level": "autonomous", "max_daily_spend_cents": 50000, "max_budget_increase_percent": 20, "max_automated_actions_per_day": 3, "auto_executable_action_types": ["pause_ad"]},
        headers=org_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["autonomy_level"] == "autonomous"
    assert resp.json()["max_budget_increase_percent"] == 20


def test_emergency_stop_toggle(client, seeded_roles, db_session):
    org_headers, campaign_id = _register_org_with_campaign(client, db_session)
    stop_resp = client.post(f"/api/v1/optimization/meta-campaigns/{campaign_id}/emergency-stop", json={"stopped": True, "reason": "Testing"}, headers=org_headers)
    assert stop_resp.status_code == 200
    assert stop_resp.json()["is_emergency_stopped"] is True
    assert stop_resp.json()["emergency_stop_reason"] == "Testing"

    resume_resp = client.post(f"/api/v1/optimization/meta-campaigns/{campaign_id}/emergency-stop", json={"stopped": False}, headers=org_headers)
    assert resume_resp.status_code == 200
    assert resume_resp.json()["is_emergency_stopped"] is False


def test_whitelist_add_check_remove(client, seeded_roles, db_session):
    org_headers, campaign_id = _register_org_with_campaign(client, db_session)

    not_whitelisted = client.get(f"/api/v1/optimization/meta-campaigns/{campaign_id}/whitelist", headers=org_headers)
    assert not_whitelisted.status_code == 200
    assert not_whitelisted.json() is None

    add_resp = client.post(f"/api/v1/optimization/meta-campaigns/{campaign_id}/whitelist", headers=org_headers)
    assert add_resp.status_code == 201

    now_whitelisted = client.get(f"/api/v1/optimization/meta-campaigns/{campaign_id}/whitelist", headers=org_headers)
    assert now_whitelisted.json() is not None

    remove_resp = client.delete(f"/api/v1/optimization/meta-campaigns/{campaign_id}/whitelist", headers=org_headers)
    assert remove_resp.status_code == 204

    after_remove = client.get(f"/api/v1/optimization/meta-campaigns/{campaign_id}/whitelist", headers=org_headers)
    assert after_remove.json() is None


def test_list_and_review_decision(client, seeded_roles, db_session):
    org_headers, campaign_id = _register_org_with_campaign(client, db_session)
    org_id = org_headers["X-Organization-Id"]

    decision = OptimizationDecision(
        organization_id=uuid.UUID(org_id), meta_campaign_id=uuid.UUID(campaign_id), observation="CTR dropped 40%",
        evidence_json={"signal": "CTR"}, action_type=OptimizationActionType.PAUSE_AD, proposed_action="Pause the underperforming ad",
        action_payload={}, expected_outcome="May help, not guaranteed", confidence=0.7, risk=DecisionRisk.LOW,
        required_permission="can_manage_campaigns", status=DecisionStatus.RECOMMENDED,
    )
    db_session.add(decision)
    db_session.commit()

    list_resp = client.get("/api/v1/optimization/decisions", headers=org_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1
    assert list_resp.json()[0]["observation"] == "CTR dropped 40%"

    reject_resp = client.post(f"/api/v1/optimization/decisions/{decision.id}/review", json={"approve": False}, headers=org_headers)
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "rejected"


def test_optimization_resources_isolated_across_organizations(client, seeded_roles, db_session):
    org_a_headers, campaign_id_a = _register_org_with_campaign(client, db_session)
    org_b_headers, _ = _register_org_with_campaign(client, db_session)

    exploit_resp = client.get(f"/api/v1/optimization/meta-campaigns/{campaign_id_a}/autonomy-settings", headers=org_b_headers)
    assert exploit_resp.status_code == 404
