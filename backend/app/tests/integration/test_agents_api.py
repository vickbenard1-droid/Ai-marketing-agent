"""
Integration tests for /api/v1/agents/*.

Mocking approach: httpx.Client.post cannot be patched globally here,
because Starlette's TestClient is itself built on httpx.Client — a global
patch intercepts the test's own requests to the app, not just the
outbound call to the AI provider (confirmed by reproducing the failure
directly; see git history). Instead, app.ai_providers.factory.
get_ai_provider_for_task is monkeypatched to return a ClaudeProvider
constructed with an httpx.MockTransport, which only intercepts that
provider's own httpx.Client instance.
"""
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


def _mocked_claude_provider(text: str, *, input_tokens: int = 40, output_tokens: int = 80):
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
    """Patches the factory function everywhere it's imported by name —
    both app.agents._shared and app.ai_chat.service import it directly
    into their own namespace, so both need patching for full coverage."""
    monkeypatch.setattr("app.agents._shared.get_ai_provider_for_task", lambda task: provider)
    monkeypatch.setattr("app.ai_chat.service.get_ai_provider_for_task", lambda task: provider)


def test_list_agents_returns_all_four(client, seeded_roles):
    headers = _register_and_org_headers(client)
    resp = client.get("/api/v1/agents", headers=headers)
    assert resp.status_code == 200
    names = {a["name"] for a in resp.json()}
    assert names == {
        "marketing_strategy_agent",
        "audience_research_agent",
        "ad_copy_agent",
        "seo_agent",
    }


def test_list_agents_requires_can_execute_ai_actions(client, seeded_roles):
    """RBAC: a Viewer (can_execute_ai_actions=False) must be rejected."""
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

    resp = client.get("/api/v1/agents", headers=viewer_headers)
    assert resp.status_code == 403


def test_run_marketing_strategy_agent_succeeds(client, seeded_roles, monkeypatch):
    _patch_provider(monkeypatch, _mocked_claude_provider("Here is your marketing strategy..."))
    headers = _register_and_org_headers(client)

    resp = client.post("/api/v1/agents/marketing_strategy_agent/run", json={}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "marketing strategy" in body["output"]
    assert body["requires_human_approval"] is False


def test_run_ad_copy_agent_without_brief_fails_cleanly(client, seeded_roles, monkeypatch):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"content": [], "usage": {}})

    provider = ClaudeProvider(api_key="test-key", transport=httpx.MockTransport(handler))
    _patch_provider(monkeypatch, provider)
    headers = _register_and_org_headers(client)

    resp = client.post("/api/v1/agents/ad_copy_agent/run", json={}, headers=headers)
    assert resp.status_code == 200  # not an HTTP error — a clean "couldn't run" result
    body = resp.json()
    assert body["success"] is False
    assert "brief" in body["notes"].lower()
    assert len(calls) == 0  # never reached the AI provider


def test_run_ad_copy_agent_with_brief_succeeds(client, seeded_roles, monkeypatch):
    _patch_provider(monkeypatch, _mocked_claude_provider("Headline: Light Up Your Home"))
    headers = _register_and_org_headers(client)

    resp = client.post(
        "/api/v1/agents/ad_copy_agent/run",
        json={"brief": "Write ad copy for our lavender candle"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_run_unknown_agent_returns_404(client, seeded_roles):
    headers = _register_and_org_headers(client)
    resp = client.post("/api/v1/agents/not_a_real_agent/run", json={}, headers=headers)
    assert resp.status_code == 404


def test_running_agent_records_usage(client, seeded_roles, db_session, monkeypatch):
    _patch_provider(monkeypatch, _mocked_claude_provider("Strategy output", input_tokens=40, output_tokens=80))
    headers = _register_and_org_headers(client)

    client.post("/api/v1/agents/marketing_strategy_agent/run", json={}, headers=headers)

    from app.models.ai_usage_log import AIUsageLog

    logs = db_session.query(AIUsageLog).all()
    assert len(logs) == 1
    assert logs[0].succeeded is True
    assert logs[0].input_tokens == 40
    assert logs[0].output_tokens == 80


def test_run_agent_requires_can_execute_ai_actions(client, seeded_roles):
    owner_headers = _register_and_org_headers(client)
    org_id = owner_headers["X-Organization-Id"]

    analyst_email = unique_email()
    analyst_resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": analyst_email,
            "password": "supersecret123",
            "full_name": "Analyst",
            "organization_name": "Analyst Org",
        },
    )
    analyst_token = analyst_resp.json()["access_token"]
    client.post(
        "/api/v1/organizations/current/members",
        json={"email": analyst_email, "role_name": "analyst"},
        headers=owner_headers,
    )
    analyst_headers = {"Authorization": f"Bearer {analyst_token}", "X-Organization-Id": org_id}

    resp = client.post("/api/v1/agents/marketing_strategy_agent/run", json={}, headers=analyst_headers)
    assert resp.status_code == 403
