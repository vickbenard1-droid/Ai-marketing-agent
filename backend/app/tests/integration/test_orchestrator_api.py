"""
Functional (HTTP-level) tests for /api/v1/orchestrator/* - the Week 11
orchestrator's actual create/advance/list/activity/memory endpoints.
Complements test_orchestrator_service.py (which tests the human-control
security fix directly against the service layer, not through HTTP) by
exercising the same flows through the real API surface a frontend
would actually call.
"""
import json

import httpx

from app.ai_providers.claude_provider import ClaudeProvider
from app.tests.conftest import unique_email


def _register_org(client):
    email = unique_email()
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": "supersecret123", "full_name": "U", "organization_name": f"Org {email}"})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    org_id = client.get("/api/v1/organizations", headers=headers).json()[0]["id"]
    return {**headers, "X-Organization-Id": org_id}


def _mock_plan(monkeypatch, plan: dict):
    import app.orchestrator.service as orch_svc

    def handler(request):
        return httpx.Response(200, json={"content": [{"type": "text", "text": json.dumps(plan)}], "usage": {"input_tokens": 100, "output_tokens": 40}})
    monkeypatch.setattr(orch_svc, "get_ai_provider_for_task", lambda task: ClaudeProvider(api_key="test-key", transport=httpx.MockTransport(handler)))


def test_list_available_agents(client, seeded_roles):
    org_headers = _register_org(client)
    resp = client.get("/api/v1/orchestrator/agents", headers=org_headers)
    assert resp.status_code == 200
    names = {a["name"] for a in resp.json()}
    assert "analytics_agent" in names
    assert "advertising_agent" in names


def test_create_and_list_runs(client, seeded_roles, seeded_plans, monkeypatch):
    org_headers = _register_org(client)
    plan = {"steps": [{"agent_name": "analytics_agent", "action_description": "Review performance", "requires_approval": False}], "plan_summary": "Review then report"}
    _mock_plan(monkeypatch, plan)

    create_resp = client.post("/api/v1/orchestrator/runs", json={"goal_text": "Help me get 100 sales"}, headers=org_headers)
    assert create_resp.status_code == 201
    assert create_resp.json()["status"] == "running"
    assert create_resp.json()["goal_text"] == "Help me get 100 sales"

    list_resp = client.get("/api/v1/orchestrator/runs", headers=org_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


def test_advance_run_and_view_activity(client, seeded_roles, seeded_plans, monkeypatch):
    org_headers = _register_org(client)
    plan = {"steps": [{"agent_name": "analytics_agent", "action_description": "Review performance", "requires_approval": False}], "plan_summary": "x"}
    _mock_plan(monkeypatch, plan)

    run = client.post("/api/v1/orchestrator/runs", json={"goal_text": "Review performance"}, headers=org_headers).json()

    advance_resp = client.post(f"/api/v1/orchestrator/runs/{run['id']}/advance", headers=org_headers)
    assert advance_resp.status_code == 200
    assert advance_resp.json()["status"] == "completed"

    activity_resp = client.get(f"/api/v1/orchestrator/runs/{run['id']}/activity", headers=org_headers)
    assert activity_resp.status_code == 200
    assert len(activity_resp.json()) == 1
    assert activity_resp.json()[0]["agent_name"] == "analytics_agent"
    assert activity_resp.json()[0]["status"] == "completed"


def test_advance_run_pauses_for_approval_step(client, seeded_roles, seeded_plans, monkeypatch):
    org_headers = _register_org(client)
    plan = {"steps": [{"agent_name": "advertising_agent", "action_description": "Launch a campaign", "requires_approval": True}], "plan_summary": "x"}
    _mock_plan(monkeypatch, plan)

    run = client.post("/api/v1/orchestrator/runs", json={"goal_text": "Launch a campaign"}, headers=org_headers).json()
    advance_resp = client.post(f"/api/v1/orchestrator/runs/{run['id']}/advance", headers=org_headers)
    assert advance_resp.status_code == 200
    assert advance_resp.json()["status"] == "paused_for_approval"


def test_reject_paused_step_cancels_run(client, seeded_roles, seeded_plans, monkeypatch):
    org_headers = _register_org(client)
    plan = {"steps": [{"agent_name": "advertising_agent", "action_description": "Launch a campaign", "requires_approval": True}], "plan_summary": "x"}
    _mock_plan(monkeypatch, plan)

    run = client.post("/api/v1/orchestrator/runs", json={"goal_text": "Launch a campaign"}, headers=org_headers).json()
    client.post(f"/api/v1/orchestrator/runs/{run['id']}/advance", headers=org_headers)

    reject_resp = client.post(f"/api/v1/orchestrator/runs/{run['id']}/approve-step", json={"approve": False}, headers=org_headers)
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "cancelled"


def test_org_wide_activity_and_memory_endpoints_reachable(client, seeded_roles, seeded_plans, monkeypatch):
    org_headers = _register_org(client)
    plan = {"steps": [{"agent_name": "analytics_agent", "action_description": "Review", "requires_approval": False}], "plan_summary": "x"}
    _mock_plan(monkeypatch, plan)

    run = client.post("/api/v1/orchestrator/runs", json={"goal_text": "Review"}, headers=org_headers).json()
    client.post(f"/api/v1/orchestrator/runs/{run['id']}/advance", headers=org_headers)

    activity_resp = client.get("/api/v1/orchestrator/activity", headers=org_headers)
    assert activity_resp.status_code == 200
    assert len(activity_resp.json()) >= 1

    decisions_resp = client.get("/api/v1/orchestrator/decisions", headers=org_headers)
    assert decisions_resp.status_code == 200

    memory_resp = client.get("/api/v1/orchestrator/memory", headers=org_headers)
    assert memory_resp.status_code == 200
    assert "business_knowledge" in memory_resp.json()


def test_runs_isolated_across_organizations(client, seeded_roles, seeded_plans, monkeypatch):
    org_a_headers = _register_org(client)
    org_b_headers = _register_org(client)
    plan = {"steps": [{"agent_name": "analytics_agent", "action_description": "x", "requires_approval": False}], "plan_summary": "x"}
    _mock_plan(monkeypatch, plan)

    run = client.post("/api/v1/orchestrator/runs", json={"goal_text": "Org A's private goal"}, headers=org_a_headers).json()

    exploit_resp = client.get(f"/api/v1/orchestrator/runs/{run['id']}", headers=org_b_headers)
    assert exploit_resp.status_code == 404

    org_b_runs = client.get("/api/v1/orchestrator/runs", headers=org_b_headers).json()
    assert len(org_b_runs) == 0
