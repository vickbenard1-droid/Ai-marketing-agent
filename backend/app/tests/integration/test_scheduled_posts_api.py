"""
Integration tests for /api/v1/scheduled-posts/*.

publish_scheduled_post is dispatched via .delay() from these endpoints -
task_always_eager runs it synchronously in-process, but the task opens
its own SessionLocal() rather than using the request's db_session, so
tests that exercise publish-now/retry monkeypatch
app.publishing.tasks.SessionLocal to point at the same StaticPool-backed
connection db_session/client already use - same pattern as
app/tests/unit/test_publishing_tasks.py.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import httpx
from sqlalchemy.orm import sessionmaker

import app.publishing.tasks as tasks
from app.ai_providers.claude_provider import ClaudeProvider
from app.core.config import settings
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


def _mock_token_post(self, url, **kwargs):
    return httpx.Response(
        200,
        json={"access_token": "real-tok", "refresh_token": "real-refresh", "expires_in": 3600, "scope": "x"},
    )


def _connect_facebook_account(client, headers, monkeypatch):
    monkeypatch.setattr(settings, "FACEBOOK_CLIENT_ID", "test-id")
    monkeypatch.setattr(settings, "FACEBOOK_CLIENT_SECRET", "test-secret")
    project = client.post("/api/v1/projects", json={"name": "Default"}, headers=headers).json()

    start = client.post(
        "/api/v1/oauth/facebook_page/connect", json={"project_id": project["id"]}, headers=headers
    )
    state_value = parse_qs(urlparse(start.json()["authorize_url"]).query)["state"][0]

    with patch("httpx.Client.post", _mock_token_post):
        client.get(
            "/api/v1/oauth/facebook_page/callback",
            params={"code": "authcode", "state": state_value},
            follow_redirects=False,
        )

    accounts = client.get("/api/v1/connected-accounts", headers=headers).json()
    return accounts[0]["id"], project["id"]


def _mocked_ai_provider(text: str):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"content": [{"type": "text", "text": text}], "usage": {"input_tokens": 10, "output_tokens": 10}},
        )

    return ClaudeProvider(api_key="test-key", transport=httpx.MockTransport(handler))


def _mocked_facebook_publisher(post_id_to_return: str):
    """
    Uses ContentPublisher's injectable-transport seam (added specifically
    for this) rather than patching httpx.Client.post globally — a global
    patch would also intercept FastAPI's own TestClient, which is itself
    httpx-based (the exact incident this fixes; see
    app/publishing/base.py's own docstring on the transport parameter).
    """
    from app.publishing.platforms.facebook import FacebookPublisher

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": post_id_to_return})

    transport = httpx.MockTransport(handler)
    publisher = FacebookPublisher()
    original_publish = publisher.publish
    publisher.publish = lambda *, access_token, request: original_publish(
        access_token=access_token, request=request, transport=transport
    )
    return publisher


def _create_content(client, headers, monkeypatch):
    monkeypatch.setattr(
        "app.content.generation_service.get_ai_provider_for_task",
        lambda task: _mocked_ai_provider("Check out our candles!"),
    )
    resp = client.post(
        "/api/v1/content/generate",
        json={"content_type": "facebook_post", "source_text": "candles"},
        headers=headers,
    )
    return resp.json()["id"]


def test_create_and_schedule_post_full_flow(client, seeded_roles, monkeypatch):
    headers = _register_and_org_headers(client)
    account_id, _ = _connect_facebook_account(client, headers, monkeypatch)
    content_id = _create_content(client, headers, monkeypatch)

    draft = client.post(
        "/api/v1/scheduled-posts",
        json={"content_id": content_id, "connected_account_id": account_id},
        headers=headers,
    )
    assert draft.status_code == 201
    assert draft.json()["status"] == "draft"

    future_time = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    scheduled = client.post(
        f"/api/v1/scheduled-posts/{draft.json()['id']}/schedule",
        json={"scheduled_for": future_time},
        headers=headers,
    )
    assert scheduled.status_code == 200
    assert scheduled.json()["status"] == "scheduled"
    assert scheduled.json()["scheduled_for"] is not None


def test_cannot_schedule_in_the_past(client, seeded_roles, monkeypatch):
    headers = _register_and_org_headers(client)
    account_id, _ = _connect_facebook_account(client, headers, monkeypatch)
    content_id = _create_content(client, headers, monkeypatch)

    draft = client.post(
        "/api/v1/scheduled-posts",
        json={"content_id": content_id, "connected_account_id": account_id},
        headers=headers,
    ).json()

    past_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    resp = client.post(
        f"/api/v1/scheduled-posts/{draft['id']}/schedule", json={"scheduled_for": past_time}, headers=headers
    )
    assert resp.status_code == 400


def test_publish_now_dispatches_real_task_and_publishes(client, seeded_roles, db_session, monkeypatch):
    TestSessionLocal = sessionmaker(bind=db_session.get_bind())
    monkeypatch.setattr(tasks, "SessionLocal", TestSessionLocal)

    headers = _register_and_org_headers(client)
    account_id, _ = _connect_facebook_account(client, headers, monkeypatch)
    content_id = _create_content(client, headers, monkeypatch)

    draft = client.post(
        "/api/v1/scheduled-posts",
        json={"content_id": content_id, "connected_account_id": account_id},
        headers=headers,
    ).json()

    monkeypatch.setattr(
        "app.publishing.tasks.get_publisher",
        lambda platform_type: _mocked_facebook_publisher("fb_post_123"),
    )
    resp = client.post(f"/api/v1/scheduled-posts/{draft['id']}/publish-now", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "published"
    assert resp.json()["external_post_id"] == "fb_post_123"


def test_retry_only_works_on_failed_posts(client, seeded_roles, db_session, monkeypatch):
    TestSessionLocal = sessionmaker(bind=db_session.get_bind())
    monkeypatch.setattr(tasks, "SessionLocal", TestSessionLocal)

    headers = _register_and_org_headers(client)
    account_id, _ = _connect_facebook_account(client, headers, monkeypatch)
    content_id = _create_content(client, headers, monkeypatch)

    draft = client.post(
        "/api/v1/scheduled-posts",
        json={"content_id": content_id, "connected_account_id": account_id},
        headers=headers,
    ).json()

    resp = client.post(f"/api/v1/scheduled-posts/{draft['id']}/retry", headers=headers)
    assert resp.status_code == 400


def test_scheduled_posts_require_can_manage_content_to_create(client, seeded_roles, monkeypatch):
    owner_headers = _register_and_org_headers(client)
    org_id = owner_headers["X-Organization-Id"]
    account_id, _ = _connect_facebook_account(client, owner_headers, monkeypatch)
    content_id = _create_content(client, owner_headers, monkeypatch)

    analyst_headers = _add_member_with_role(client, owner_headers, org_id, "analyst")
    resp = client.post(
        "/api/v1/scheduled-posts",
        json={"content_id": content_id, "connected_account_id": account_id},
        headers=analyst_headers,
    )
    assert resp.status_code == 403


def test_list_scheduled_posts_requires_only_membership(client, seeded_roles, monkeypatch):
    owner_headers = _register_and_org_headers(client)
    org_id = owner_headers["X-Organization-Id"]
    account_id, _ = _connect_facebook_account(client, owner_headers, monkeypatch)
    content_id = _create_content(client, owner_headers, monkeypatch)
    client.post(
        "/api/v1/scheduled-posts",
        json={"content_id": content_id, "connected_account_id": account_id},
        headers=owner_headers,
    )

    analyst_headers = _add_member_with_role(client, owner_headers, org_id, "analyst")
    resp = client.get("/api/v1/scheduled-posts", headers=analyst_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_scheduled_posts_isolated_across_organizations(client, seeded_roles, monkeypatch):
    org_a_headers = _register_and_org_headers(client)
    org_b_headers = _register_and_org_headers(client)
    account_id, _ = _connect_facebook_account(client, org_a_headers, monkeypatch)
    content_id = _create_content(client, org_a_headers, monkeypatch)
    client.post(
        "/api/v1/scheduled-posts",
        json={"content_id": content_id, "connected_account_id": account_id},
        headers=org_a_headers,
    )

    org_b_list = client.get("/api/v1/scheduled-posts", headers=org_b_headers).json()
    assert len(org_b_list) == 0


def test_cannot_create_post_on_disconnected_account(client, seeded_roles, monkeypatch):
    headers = _register_and_org_headers(client)
    account_id, _ = _connect_facebook_account(client, headers, monkeypatch)
    content_id = _create_content(client, headers, monkeypatch)

    client.post(f"/api/v1/connected-accounts/{account_id}/disconnect", headers=headers)

    resp = client.post(
        "/api/v1/scheduled-posts",
        json={"content_id": content_id, "connected_account_id": account_id},
        headers=headers,
    )
    assert resp.status_code == 400


def test_recommend_and_accept_recommendation_flow(client, seeded_roles, monkeypatch):
    headers = _register_and_org_headers(client)
    account_id, _ = _connect_facebook_account(client, headers, monkeypatch)
    content_id = _create_content(client, headers, monkeypatch)

    draft = client.post(
        "/api/v1/scheduled-posts",
        json={"content_id": content_id, "connected_account_id": account_id},
        headers=headers,
    ).json()

    import json as jsonlib

    rec_response = {
        "recommended_platform": "facebook_page",
        "recommended_post_time": "Wednesday around 6pm",
        "recommended_format": "single image",
        "recommended_hashtags": ["#candles", "#selfcare"],
        "rationale": "Engagement for lifestyle content tends to perform well in early evening.",
    }
    monkeypatch.setattr(
        "app.scheduling.recommendation_service.get_ai_provider_for_task",
        lambda task: _mocked_ai_provider(jsonlib.dumps(rec_response)),
    )

    recommend_resp = client.post(f"/api/v1/scheduled-posts/{draft['id']}/recommend", headers=headers)
    assert recommend_resp.status_code == 200
    body = recommend_resp.json()
    assert body["ai_recommended_platform"] == "facebook_page"
    assert body["ai_recommended_hashtags"] == ["#candles", "#selfcare"]
    assert body["status"] == "draft"
    assert body["scheduled_for"] is None

    accept_resp = client.post(f"/api/v1/scheduled-posts/{draft['id']}/accept-recommendation", headers=headers)
    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] == "scheduled"
    assert accept_resp.json()["scheduled_for"] is not None
