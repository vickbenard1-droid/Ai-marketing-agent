"""
Integration tests for /api/v1/chat/*. Same MockTransport approach as
test_agents_api.py — see that file's module docstring for why
httpx.Client.post can't be patched globally when TestClient is involved.
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


def _mocked_claude_provider(text: str):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": text}],
                "usage": {"input_tokens": 20, "output_tokens": 30},
            },
        )

    return ClaudeProvider(api_key="test-key", transport=httpx.MockTransport(handler))


def _patch_provider(monkeypatch, provider):
    monkeypatch.setattr("app.agents._shared.get_ai_provider_for_task", lambda task: provider)
    monkeypatch.setattr("app.ai_chat.service.get_ai_provider_for_task", lambda task: provider)


def test_send_message_creates_conversation(client, seeded_roles, monkeypatch):
    _patch_provider(monkeypatch, _mocked_claude_provider("Your best customers are home decor shoppers."))
    headers = _register_and_org_headers(client)

    resp = client.post(
        "/api/v1/chat/messages", json={"message": "Who is my best customer?"}, headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["message"]["role"] == "assistant"
    assert "home decor" in body["message"]["content"]
    assert body["conversation_id"]


def test_send_message_continues_existing_conversation(client, seeded_roles, monkeypatch):
    _patch_provider(monkeypatch, _mocked_claude_provider("First reply"))
    headers = _register_and_org_headers(client)

    first = client.post("/api/v1/chat/messages", json={"message": "Hello"}, headers=headers)
    conversation_id = first.json()["conversation_id"]

    _patch_provider(monkeypatch, _mocked_claude_provider("Second reply"))
    second = client.post(
        "/api/v1/chat/messages",
        json={"message": "Follow up question", "conversation_id": conversation_id},
        headers=headers,
    )
    assert second.status_code == 200
    assert second.json()["conversation_id"] == conversation_id
    assert second.json()["message"]["content"] == "Second reply"


def test_send_message_to_nonexistent_conversation_returns_404(client, seeded_roles, monkeypatch):
    _patch_provider(monkeypatch, _mocked_claude_provider("reply"))
    headers = _register_and_org_headers(client)

    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = client.post(
        "/api/v1/chat/messages",
        json={"message": "hi", "conversation_id": fake_id},
        headers=headers,
    )
    assert resp.status_code == 404


def test_send_message_requires_can_execute_ai_actions(client, seeded_roles):
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

    resp = client.post("/api/v1/chat/messages", json={"message": "hi"}, headers=viewer_headers)
    assert resp.status_code == 403


def test_list_conversations(client, seeded_roles, monkeypatch):
    _patch_provider(monkeypatch, _mocked_claude_provider("reply"))
    headers = _register_and_org_headers(client)

    client.post("/api/v1/chat/messages", json={"message": "First conversation"}, headers=headers)
    client.post("/api/v1/chat/messages", json={"message": "Second conversation"}, headers=headers)

    resp = client.get("/api/v1/chat/conversations", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_conversations_does_not_require_ai_permission(client, seeded_roles):
    """Reading conversation history is a read concern — any member can do
    it, distinct from incurring cost by sending a new message."""
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

    resp = client.get("/api/v1/chat/conversations", headers=viewer_headers)
    assert resp.status_code == 200


def test_get_conversation_detail_includes_messages(client, seeded_roles, monkeypatch):
    _patch_provider(monkeypatch, _mocked_claude_provider("The reply"))
    headers = _register_and_org_headers(client)

    sent = client.post("/api/v1/chat/messages", json={"message": "My question"}, headers=headers)
    conversation_id = sent.json()["conversation_id"]

    resp = client.get(f"/api/v1/chat/conversations/{conversation_id}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "user"
    assert body["messages"][0]["content"] == "My question"
    assert body["messages"][1]["role"] == "assistant"
    assert body["messages"][1]["content"] == "The reply"


def test_conversations_isolated_across_organizations(client, seeded_roles, monkeypatch):
    """Tenant isolation: org A's conversations must never be visible to org B."""
    _patch_provider(monkeypatch, _mocked_claude_provider("reply"))
    org_a_headers = _register_and_org_headers(client)
    org_b_headers = _register_and_org_headers(client)

    sent = client.post(
        "/api/v1/chat/messages", json={"message": "Org A's question"}, headers=org_a_headers
    )
    conversation_id = sent.json()["conversation_id"]

    # Org B cannot list it...
    org_b_conversations = client.get("/api/v1/chat/conversations", headers=org_b_headers).json()
    assert conversation_id not in [c["id"] for c in org_b_conversations]

    # ...and cannot fetch it directly by id either.
    resp = client.get(f"/api/v1/chat/conversations/{conversation_id}", headers=org_b_headers)
    assert resp.status_code == 404


def test_chat_records_usage(client, seeded_roles, db_session, monkeypatch):
    _patch_provider(monkeypatch, _mocked_claude_provider("reply"))
    headers = _register_and_org_headers(client)

    client.post("/api/v1/chat/messages", json={"message": "hi"}, headers=headers)

    from app.models.ai_usage_log import AIUsageLog, AIUsageSource

    logs = db_session.query(AIUsageLog).filter(AIUsageLog.source == AIUsageSource.CHAT).all()
    assert len(logs) == 1
    assert logs[0].input_tokens == 20
    assert logs[0].output_tokens == 30
