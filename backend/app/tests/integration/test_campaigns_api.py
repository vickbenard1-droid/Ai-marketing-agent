"""
Integration tests for the campaign builder endpoints. Same MockTransport
approach as test_agents_api.py — see that file's module docstring.
"""
import json

import httpx

from app.ai_providers.claude_provider import ClaudeProvider
from app.tests.conftest import unique_email

VALID_CAMPAIGN_RESPONSE = {
    "strategy": {
        "objective": "Generate qualified leads",
        "funnel_stage": "consideration",
        "target_customer": "Parents seeking school admission",
        "pain_points": ["finding a good school", "application deadlines"],
        "value_proposition": "Simple application process",
        "offer": "Early bird discount",
        "cta": "Apply Now",
    },
    "audience": {
        "demographics": "Parents 30-45",
        "geography": "Lagos",
        "interests": ["education", "parenting"],
        "behaviors": ["searches for schools online"],
        "lookalike_strategy": "Lookalike of existing applicants",
        "retargeting_strategy": "Retarget landing page visitors",
    },
    "ad_copy_variants": [
        {
            "headline": "Secure Your Child's Spot",
            "primary_text": "Apply now.",
            "description": "Limited spots",
            "call_to_action": "Apply Now",
        },
        {
            "headline": "Enrollment Open Now",
            "primary_text": "Join our school.",
            "description": "Great teachers",
            "call_to_action": "Learn More",
        },
        {
            "headline": "Give Your Child The Best Start",
            "primary_text": "Quality education awaits.",
            "description": "Trusted by parents",
            "call_to_action": "Apply Now",
        },
    ],
    "creative_concepts": [
        {"concept_type": "image", "title": "Happy students", "description": "Bright classroom photo"},
        {"concept_type": "video", "title": "Campus tour", "description": "30 second walkthrough"},
        {"concept_type": "hook", "title": "Parent testimonial hook", "description": "Open with a parent quote"},
        {"concept_type": "ugc", "title": "Student day-in-the-life", "description": "Authentic student content"},
    ],
    "budget_strategy": {
        "test_budget": "50000 NGN",
        "ad_set_count": 3,
        "budget_allocation": "Even split across 3 ad sets",
        "testing_period_days": 7,
        "scaling_rules": "Scale winning ad set by 20% every 3 days",
    },
}


def _register_and_org_headers(client):
    email = unique_email()
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "supersecret123",
            "full_name": "Test User",
            "organization_name": "Acme School",
        },
    )
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    orgs = client.get("/api/v1/organizations", headers=headers).json()
    return {**headers, "X-Organization-Id": orgs[0]["id"]}


def _mocked_claude_provider(response_dict: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": json.dumps(response_dict)}],
                "usage": {"input_tokens": 200, "output_tokens": 600},
            },
        )

    return ClaudeProvider(api_key="test-key", transport=httpx.MockTransport(handler))


def _patch_provider(monkeypatch, provider):
    """Patches the factory function everywhere it's imported by name —
    app.campaigns.generation_service imports it directly, same pattern as
    app.agents._shared and app.ai_chat.service."""
    monkeypatch.setattr("app.campaigns.generation_service.get_ai_provider_for_task", lambda task: provider)


def _add_member_with_role(client, owner_headers, org_id, role_name):
    email = unique_email()
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "supersecret123",
            "full_name": role_name.title(),
            "organization_name": f"{role_name} org",
        },
    )
    token = resp.json()["access_token"]
    client.post(
        "/api/v1/organizations/current/members",
        json={"email": email, "role_name": role_name},
        headers=owner_headers,
    )
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


def _create_draft(client, headers, **overrides):
    payload = {
        "product_name": "School admission forms",
        "objective": "leads",
        "desired_outcome_count": 100,
        "budget_amount": 300000,
        "budget_currency": "NGN",
        "target_location": "Lagos, Nigeria",
        **overrides,
    }
    return client.post("/api/v1/campaigns", json=payload, headers=headers)


# --------------------------------------------------------------------------
# CRUD + RBAC
# --------------------------------------------------------------------------
def test_create_campaign_draft(client, seeded_roles):
    headers = _register_and_org_headers(client)
    resp = _create_draft(client, headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "draft"
    assert body["product_name"] == "School admission forms"
    assert body["budget_amount"] == 300000


def test_create_campaign_requires_can_manage_campaigns(client, seeded_roles):
    owner_headers = _register_and_org_headers(client)
    org_id = owner_headers["X-Organization-Id"]
    viewer_headers = _add_member_with_role(client, owner_headers, org_id, "viewer")

    resp = _create_draft(client, viewer_headers)
    assert resp.status_code == 403


def test_list_campaigns_only_requires_membership(client, seeded_roles):
    owner_headers = _register_and_org_headers(client)
    org_id = owner_headers["X-Organization-Id"]
    _create_draft(client, owner_headers)

    analyst_headers = _add_member_with_role(client, owner_headers, org_id, "analyst")
    resp = client.get("/api/v1/campaigns", headers=analyst_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_get_campaign_detail(client, seeded_roles):
    headers = _register_and_org_headers(client)
    created = _create_draft(client, headers).json()

    resp = client.get(f"/api/v1/campaigns/{created['id']}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ad_copy_variants"] == []
    assert body["strategy"] is None


def test_get_campaign_not_found(client, seeded_roles):
    headers = _register_and_org_headers(client)
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = client.get(f"/api/v1/campaigns/{fake_id}", headers=headers)
    assert resp.status_code == 404


def test_campaigns_isolated_across_organizations(client, seeded_roles):
    org_a_headers = _register_and_org_headers(client)
    org_b_headers = _register_and_org_headers(client)
    created = _create_draft(client, org_a_headers).json()

    resp = client.get(f"/api/v1/campaigns/{created['id']}", headers=org_b_headers)
    assert resp.status_code == 404

    org_b_list = client.get("/api/v1/campaigns", headers=org_b_headers).json()
    assert len(org_b_list) == 0


def test_update_campaign_draft(client, seeded_roles):
    headers = _register_and_org_headers(client)
    created = _create_draft(client, headers).json()

    resp = client.patch(
        f"/api/v1/campaigns/{created['id']}", json={"product_name": "Updated name"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["product_name"] == "Updated name"


def test_delete_campaign_draft(client, seeded_roles):
    headers = _register_and_org_headers(client)
    created = _create_draft(client, headers).json()

    resp = client.delete(f"/api/v1/campaigns/{created['id']}", headers=headers)
    assert resp.status_code == 200

    get_resp = client.get(f"/api/v1/campaigns/{created['id']}", headers=headers)
    assert get_resp.status_code == 404


# --------------------------------------------------------------------------
# Generation
# --------------------------------------------------------------------------
def test_generate_campaign_full_flow(client, seeded_roles, monkeypatch):
    _patch_provider(monkeypatch, _mocked_claude_provider(VALID_CAMPAIGN_RESPONSE))
    headers = _register_and_org_headers(client)
    created = _create_draft(client, headers).json()

    resp = client.post(f"/api/v1/campaigns/{created['id']}/generate", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "generated"
    assert len(body["ad_copy_variants"]) == 3
    assert len(body["creative_concepts"]) == 4
    assert body["strategy"]["strategy"]["cta"] == "Apply Now"
    assert body["strategy"]["budget_strategy"]["ad_set_count"] == 3


def test_generate_campaign_requires_can_execute_ai_actions(client, seeded_roles, monkeypatch):
    _patch_provider(monkeypatch, _mocked_claude_provider(VALID_CAMPAIGN_RESPONSE))
    owner_headers = _register_and_org_headers(client)
    org_id = owner_headers["X-Organization-Id"]
    created = _create_draft(client, owner_headers).json()

    analyst_headers = _add_member_with_role(client, owner_headers, org_id, "analyst")
    resp = client.post(f"/api/v1/campaigns/{created['id']}/generate", headers=analyst_headers)
    assert resp.status_code == 403


def test_generate_campaign_records_usage(client, seeded_roles, db_session, monkeypatch):
    _patch_provider(monkeypatch, _mocked_claude_provider(VALID_CAMPAIGN_RESPONSE))
    headers = _register_and_org_headers(client)
    created = _create_draft(client, headers).json()

    client.post(f"/api/v1/campaigns/{created['id']}/generate", headers=headers)

    from app.models.ai_usage_log import AIUsageLog, AIUsageSource

    logs = db_session.query(AIUsageLog).filter(AIUsageLog.source == AIUsageSource.CAMPAIGN_BUILDER).all()
    assert len(logs) == 1
    assert logs[0].input_tokens == 200
    assert logs[0].output_tokens == 600


def test_generate_campaign_with_malformed_ai_response_returns_502(client, seeded_roles, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "Sorry, I can't help with that."}],
                "usage": {"input_tokens": 10, "output_tokens": 10},
            },
        )

    provider = ClaudeProvider(api_key="test-key", transport=httpx.MockTransport(handler))
    _patch_provider(monkeypatch, provider)
    headers = _register_and_org_headers(client)
    created = _create_draft(client, headers).json()

    resp = client.post(f"/api/v1/campaigns/{created['id']}/generate", headers=headers)
    assert resp.status_code == 502

    detail = client.get(f"/api/v1/campaigns/{created['id']}", headers=headers).json()
    assert detail["status"] == "draft"


def test_regenerate_replaces_prior_variants(client, seeded_roles, monkeypatch):
    _patch_provider(monkeypatch, _mocked_claude_provider(VALID_CAMPAIGN_RESPONSE))
    headers = _register_and_org_headers(client)
    created = _create_draft(client, headers).json()

    client.post(f"/api/v1/campaigns/{created['id']}/generate", headers=headers)

    smaller_response = {**VALID_CAMPAIGN_RESPONSE, "ad_copy_variants": VALID_CAMPAIGN_RESPONSE["ad_copy_variants"][:1]}
    _patch_provider(monkeypatch, _mocked_claude_provider(smaller_response))
    second = client.post(f"/api/v1/campaigns/{created['id']}/generate", headers=headers)

    assert len(second.json()["ad_copy_variants"]) == 1  # replaced, not appended (would be 4 if appended)


# --------------------------------------------------------------------------
# Ad copy variant editing + approval
# --------------------------------------------------------------------------
def test_edit_ad_copy_variant(client, seeded_roles, monkeypatch):
    _patch_provider(monkeypatch, _mocked_claude_provider(VALID_CAMPAIGN_RESPONSE))
    headers = _register_and_org_headers(client)
    created = _create_draft(client, headers).json()
    generated = client.post(f"/api/v1/campaigns/{created['id']}/generate", headers=headers).json()
    variant_id = generated["ad_copy_variants"][0]["id"]

    resp = client.patch(
        f"/api/v1/campaigns/{created['id']}/ad-copy-variants/{variant_id}",
        json={"headline": "My Custom Edited Headline"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["headline"] == "My Custom Edited Headline"
    assert resp.json()["is_edited"] is True


def test_approve_campaign_requires_generated_status(client, seeded_roles):
    headers = _register_and_org_headers(client)
    created = _create_draft(client, headers).json()

    resp = client.post(f"/api/v1/campaigns/{created['id']}/approve", headers=headers)
    assert resp.status_code == 400


def test_approve_campaign_full_flow(client, seeded_roles, monkeypatch):
    _patch_provider(monkeypatch, _mocked_claude_provider(VALID_CAMPAIGN_RESPONSE))
    headers = _register_and_org_headers(client)
    created = _create_draft(client, headers).json()
    client.post(f"/api/v1/campaigns/{created['id']}/generate", headers=headers)

    resp = client.post(f"/api/v1/campaigns/{created['id']}/approve", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    assert resp.json()["approved_at"] is not None


def test_cannot_edit_approved_campaign(client, seeded_roles, monkeypatch):
    _patch_provider(monkeypatch, _mocked_claude_provider(VALID_CAMPAIGN_RESPONSE))
    headers = _register_and_org_headers(client)
    created = _create_draft(client, headers).json()
    client.post(f"/api/v1/campaigns/{created['id']}/generate", headers=headers)
    client.post(f"/api/v1/campaigns/{created['id']}/approve", headers=headers)

    resp = client.patch(
        f"/api/v1/campaigns/{created['id']}", json={"product_name": "Trying to edit"}, headers=headers
    )
    assert resp.status_code == 400


# --------------------------------------------------------------------------
# Experiments
# --------------------------------------------------------------------------
def test_create_headline_experiment(client, seeded_roles, monkeypatch):
    _patch_provider(monkeypatch, _mocked_claude_provider(VALID_CAMPAIGN_RESPONSE))
    headers = _register_and_org_headers(client)
    created = _create_draft(client, headers).json()
    generated = client.post(f"/api/v1/campaigns/{created['id']}/generate", headers=headers).json()
    variant_ids = [v["id"] for v in generated["ad_copy_variants"][:2]]

    resp = client.post(
        f"/api/v1/campaigns/{created['id']}/experiments",
        json={"name": "Headline test", "dimension": "headline", "variant_ids": variant_ids},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["dimension"] == "headline"
    assert set(resp.json()["variant_ids"]) == set(variant_ids)


def test_create_experiment_with_unknown_variant_id_fails(client, seeded_roles, monkeypatch):
    _patch_provider(monkeypatch, _mocked_claude_provider(VALID_CAMPAIGN_RESPONSE))
    headers = _register_and_org_headers(client)
    created = _create_draft(client, headers).json()
    generated = client.post(f"/api/v1/campaigns/{created['id']}/generate", headers=headers).json()
    real_id = generated["ad_copy_variants"][0]["id"]
    fake_id = "00000000-0000-0000-0000-000000000000"

    resp = client.post(
        f"/api/v1/campaigns/{created['id']}/experiments",
        json={"name": "Bad test", "dimension": "headline", "variant_ids": [real_id, fake_id]},
        headers=headers,
    )
    assert resp.status_code == 400


def test_create_audience_experiment_with_freeform_strings(client, seeded_roles):
    headers = _register_and_org_headers(client)
    created = _create_draft(client, headers).json()

    resp = client.post(
        f"/api/v1/campaigns/{created['id']}/experiments",
        json={
            "name": "Audience test",
            "dimension": "audience",
            "variant_ids": ["Parents 25-35", "Parents 36-50"],
        },
        headers=headers,
    )
    assert resp.status_code == 201


def test_list_experiments(client, seeded_roles):
    headers = _register_and_org_headers(client)
    created = _create_draft(client, headers).json()
    client.post(
        f"/api/v1/campaigns/{created['id']}/experiments",
        json={"name": "Test", "dimension": "audience", "variant_ids": ["A", "B"]},
        headers=headers,
    )

    resp = client.get(f"/api/v1/campaigns/{created['id']}/experiments", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
