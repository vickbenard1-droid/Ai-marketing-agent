import httpx

from app.ai_providers.claude_provider import ClaudeProvider
from app.tests.conftest import unique_email


def _register_and_org_headers(client):
    email = unique_email()
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "supersecret123",
            "full_name": "Test User",
            "organization_name": "Acme Candles",
        },
    )
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    orgs = client.get("/api/v1/organizations", headers=headers).json()
    return {**headers, "X-Organization-Id": orgs[0]["id"]}


def _mocked_claude_provider(text: str, input_tokens: int = 100, output_tokens: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": text}],
                "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
            },
        )

    return ClaudeProvider(api_key="test-key", transport=httpx.MockTransport(handler))


def _patch_provider(monkeypatch, provider):
    monkeypatch.setattr("app.agents._shared.get_ai_provider_for_task", lambda task: provider)
    monkeypatch.setattr("app.ai_chat.service.get_ai_provider_for_task", lambda task: provider)


def test_usage_summary_empty_before_any_ai_call(client, seeded_roles):
    headers = _register_and_org_headers(client)
    resp = client.get("/api/v1/ai-usage/summary", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_calls"] == 0
    assert body["total_input_tokens"] == 0
    assert body["total_estimated_cost_usd"] is None


def test_usage_summary_aggregates_across_agent_and_chat_calls(client, seeded_roles, monkeypatch):
    _patch_provider(monkeypatch, _mocked_claude_provider("output", input_tokens=100, output_tokens=200))
    headers = _register_and_org_headers(client)

    client.post("/api/v1/agents/marketing_strategy_agent/run", json={}, headers=headers)
    client.post("/api/v1/chat/messages", json={"message": "hi"}, headers=headers)

    resp = client.get("/api/v1/ai-usage/summary", headers=headers)
    body = resp.json()
    assert body["total_calls"] == 2
    assert body["successful_calls"] == 2
    assert body["total_input_tokens"] == 200
    assert body["total_output_tokens"] == 400
    assert body["by_source"]["marketing_strategy_agent"] == 1
    assert body["by_source"]["chat"] == 1


def test_usage_summary_does_not_require_ai_permission(client, seeded_roles):
    """Viewing spend is a read concern, not gated behind can_execute_ai_actions."""
    owner_headers = _register_and_org_headers(client)
    org_id = owner_headers["X-Organization-Id"]

    viewer_email = unique_email()
    viewer_resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": viewer_email,
            "password": "supersecret123",
            "full_name": "Viewer",
            "organization_name": "Viewer Org",
        },
    )
    viewer_token = viewer_resp.json()["access_token"]
    client.post(
        "/api/v1/organizations/current/members",
        json={"email": viewer_email, "role_name": "viewer"},
        headers=owner_headers,
    )
    viewer_headers = {"Authorization": f"Bearer {viewer_token}", "X-Organization-Id": org_id}

    resp = client.get("/api/v1/ai-usage/summary", headers=viewer_headers)
    assert resp.status_code == 200


def test_usage_summary_isolated_across_organizations(client, seeded_roles, monkeypatch):
    _patch_provider(monkeypatch, _mocked_claude_provider("output"))
    org_a_headers = _register_and_org_headers(client)
    org_b_headers = _register_and_org_headers(client)

    client.post("/api/v1/agents/marketing_strategy_agent/run", json={}, headers=org_a_headers)

    org_a_summary = client.get("/api/v1/ai-usage/summary", headers=org_a_headers).json()
    org_b_summary = client.get("/api/v1/ai-usage/summary", headers=org_b_headers).json()

    assert org_a_summary["total_calls"] == 1
    assert org_b_summary["total_calls"] == 0
