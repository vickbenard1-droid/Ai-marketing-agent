"""
Integration tests for /api/v1/content/*, /api/v1/seo/*. Same MockTransport
approach as test_campaigns_api.py.
"""
import json

import httpx

from app.ai_providers.claude_provider import ClaudeProvider
from app.tests.conftest import unique_email

VALID_SEO_RESPONSE = {
    "primary_keyword": "lavender candle",
    "secondary_keywords": ["relaxing candle", "aromatherapy candle"],
    "search_intent": "commercial",
    "seo_title": "Lavender Candle | Relax Naturally",
    "meta_description": "Shop our lavender candle for ultimate relaxation.",
    "url_slug": "lavender-candle",
    "h1": "Our Lavender Candle",
    "h2_structure": ["Why lavender", "How to use"],
    "internal_linking_suggestions": ["Link to your about page"],
    "image_alt_text": "Lit lavender candle on wooden table",
    "hashtags": ["#lavender", "#selfcare"],
}

VALID_REPURPOSE_RESPONSE = {
    "social_posts": [
        {"platform": "facebook", "text": "Post 1"},
        {"platform": "instagram", "text": "Post 2"},
        {"platform": "linkedin", "text": "Post 3"},
        {"platform": "x", "text": "Post 4"},
        {"platform": "tiktok", "text": "Post 5"},
    ],
    "video_scripts": [
        {"title": "Script 1", "script": "Hook body CTA"},
        {"title": "Script 2", "script": "Hook body CTA"},
        {"title": "Script 3", "script": "Hook body CTA"},
    ],
    "blog_article": {"title": "Blog", "body": "Blog body"},
    "email": {"subject": "Subject", "body": "Email body"},
    "hooks": [f"Hook {i}" for i in range(10)],
}


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


def _mocked_provider_text(text: str, input_tokens=100, output_tokens=100):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": text}],
                "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
            },
        )

    return ClaudeProvider(api_key="test-key", transport=httpx.MockTransport(handler))


def _mocked_provider_json(data: dict, input_tokens=100, output_tokens=100):
    return _mocked_provider_text(json.dumps(data), input_tokens, output_tokens)


def _patch_all_providers(monkeypatch, provider):
    monkeypatch.setattr("app.content.generation_service.get_ai_provider_for_task", lambda task: provider)
    monkeypatch.setattr("app.content.repurpose_service.get_ai_provider_for_task", lambda task: provider)
    monkeypatch.setattr("app.content.seo_service.get_ai_provider_for_task", lambda task: provider)


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


# --------------------------------------------------------------------------
# Content generation
# --------------------------------------------------------------------------
def test_generate_content_full_flow(client, seeded_roles, monkeypatch):
    _patch_all_providers(monkeypatch, _mocked_provider_text("Unwind with our lavender candle."))
    headers = _register_and_org_headers(client)

    resp = client.post(
        "/api/v1/content/generate",
        json={"content_type": "instagram_caption", "source_text": "New lavender candle"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["body"] == "Unwind with our lavender candle."
    assert body["status"] == "draft"
    assert body["content_type"] == "instagram_caption"


def test_generate_content_requires_can_execute_ai_actions(client, seeded_roles, monkeypatch):
    _patch_all_providers(monkeypatch, _mocked_provider_text("output"))
    owner_headers = _register_and_org_headers(client)
    org_id = owner_headers["X-Organization-Id"]
    analyst_headers = _add_member_with_role(client, owner_headers, org_id, "analyst")

    resp = client.post(
        "/api/v1/content/generate",
        json={"content_type": "blog_post", "source_text": "hi"},
        headers=analyst_headers,
    )
    assert resp.status_code == 403


def test_generate_content_records_usage(client, seeded_roles, db_session, monkeypatch):
    _patch_all_providers(monkeypatch, _mocked_provider_text("output", input_tokens=50, output_tokens=80))
    headers = _register_and_org_headers(client)

    client.post(
        "/api/v1/content/generate",
        json={"content_type": "email", "source_text": "New product launch"},
        headers=headers,
    )

    from app.models.ai_usage_log import AIUsageLog, AIUsageSource

    logs = db_session.query(AIUsageLog).filter(AIUsageLog.source == AIUsageSource.CONTENT_GENERATION).all()
    assert len(logs) == 1
    assert logs[0].input_tokens == 50


def test_generate_content_rejects_bad_url_scheme(client, seeded_roles):
    headers = _register_and_org_headers(client)
    resp = client.post(
        "/api/v1/content/generate",
        json={"content_type": "blog_post", "source_url": "not-a-real-url"},
        headers=headers,
    )
    assert resp.status_code == 422


# --------------------------------------------------------------------------
# Content CRUD
# --------------------------------------------------------------------------
def test_list_content_with_filters(client, seeded_roles, monkeypatch):
    _patch_all_providers(monkeypatch, _mocked_provider_text("Post about candles"))
    headers = _register_and_org_headers(client)
    client.post(
        "/api/v1/content/generate",
        json={"content_type": "facebook_post", "source_text": "candles"},
        headers=headers,
    )

    resp = client.get("/api/v1/content", params={"status": "draft"}, headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp2 = client.get("/api/v1/content", params={"status": "approved"}, headers=headers)
    assert resp2.status_code == 200
    assert len(resp2.json()) == 0

    resp3 = client.get("/api/v1/content", params={"search": "candles"}, headers=headers)
    assert len(resp3.json()) == 1
    resp4 = client.get("/api/v1/content", params={"search": "nonexistent"}, headers=headers)
    assert len(resp4.json()) == 0


def test_update_and_approve_content(client, seeded_roles, monkeypatch):
    _patch_all_providers(monkeypatch, _mocked_provider_text("Original body"))
    headers = _register_and_org_headers(client)
    created = client.post(
        "/api/v1/content/generate", json={"content_type": "blog_post", "source_text": "x"}, headers=headers
    ).json()

    updated = client.patch(
        f"/api/v1/content/{created['id']}", json={"body": "Edited body"}, headers=headers
    )
    assert updated.status_code == 200
    assert updated.json()["body"] == "Edited body"

    approved = client.post(f"/api/v1/content/{created['id']}/approve", headers=headers)
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    cannot_edit = client.patch(
        f"/api/v1/content/{created['id']}", json={"body": "Try again"}, headers=headers
    )
    assert cannot_edit.status_code == 400


def test_content_isolated_across_organizations(client, seeded_roles, monkeypatch):
    _patch_all_providers(monkeypatch, _mocked_provider_text("output"))
    org_a_headers = _register_and_org_headers(client)
    org_b_headers = _register_and_org_headers(client)

    created = client.post(
        "/api/v1/content/generate", json={"content_type": "blog_post", "source_text": "x"}, headers=org_a_headers
    ).json()

    resp = client.get(f"/api/v1/content/{created['id']}", headers=org_b_headers)
    assert resp.status_code == 404

    org_b_list = client.get("/api/v1/content", headers=org_b_headers).json()
    assert len(org_b_list) == 0


def test_delete_content_requires_can_manage_content(client, seeded_roles, monkeypatch):
    _patch_all_providers(monkeypatch, _mocked_provider_text("output"))
    owner_headers = _register_and_org_headers(client)
    org_id = owner_headers["X-Organization-Id"]
    created = client.post(
        "/api/v1/content/generate", json={"content_type": "blog_post", "source_text": "x"}, headers=owner_headers
    ).json()

    analyst_headers = _add_member_with_role(client, owner_headers, org_id, "analyst")
    resp = client.delete(f"/api/v1/content/{created['id']}", headers=analyst_headers)
    assert resp.status_code == 403


# --------------------------------------------------------------------------
# Repurposing
# --------------------------------------------------------------------------
def test_repurpose_content_full_flow(client, seeded_roles, monkeypatch):
    _patch_all_providers(monkeypatch, _mocked_provider_json(VALID_REPURPOSE_RESPONSE))
    headers = _register_and_org_headers(client)

    resp = client.post(
        "/api/v1/content/repurpose",
        json={"source_text": "We just launched a new candle line"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 20  # 5 posts + 3 scripts + 1 blog + 1 email + 10 hooks

    from collections import Counter

    counts = Counter(item["content_type"] for item in body["items"])
    assert counts["hook"] == 10
    assert counts["video_script"] == 3
    assert counts["blog_post"] == 1
    assert counts["email"] == 1


def test_repurpose_requires_at_least_one_source(client, seeded_roles):
    headers = _register_and_org_headers(client)
    resp = client.post("/api/v1/content/repurpose", json={}, headers=headers)
    assert resp.status_code == 400


def test_get_repurpose_batch(client, seeded_roles, monkeypatch):
    _patch_all_providers(monkeypatch, _mocked_provider_json(VALID_REPURPOSE_RESPONSE))
    headers = _register_and_org_headers(client)
    created = client.post(
        "/api/v1/content/repurpose", json={"source_text": "New product"}, headers=headers
    ).json()

    resp = client.get(f"/api/v1/content/repurpose-batches/{created['id']}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 20


# --------------------------------------------------------------------------
# SEO
# --------------------------------------------------------------------------
def test_generate_seo_full_flow(client, seeded_roles, monkeypatch):
    _patch_all_providers(monkeypatch, _mocked_provider_json(VALID_SEO_RESPONSE))
    headers = _register_and_org_headers(client)

    resp = client.post(
        "/api/v1/seo/generate", json={"topic": "Lavender candle landing page"}, headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["primary_keyword"] == "lavender candle"
    assert body["hashtags"] == ["#lavender", "#selfcare"]
    assert "search_volume" not in body


def test_generate_seo_linked_to_content(client, seeded_roles, monkeypatch):
    _patch_all_providers(monkeypatch, _mocked_provider_text("Blog content"))
    headers = _register_and_org_headers(client)
    content = client.post(
        "/api/v1/content/generate", json={"content_type": "blog_post", "source_text": "x"}, headers=headers
    ).json()

    _patch_all_providers(monkeypatch, _mocked_provider_json(VALID_SEO_RESPONSE))
    resp = client.post(
        "/api/v1/seo/generate",
        json={"topic": "Lavender candle blog", "content_id": content["id"]},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["content_id"] == content["id"]


def test_generate_seo_requires_can_execute_ai_actions(client, seeded_roles, monkeypatch):
    _patch_all_providers(monkeypatch, _mocked_provider_json(VALID_SEO_RESPONSE))
    owner_headers = _register_and_org_headers(client)
    org_id = owner_headers["X-Organization-Id"]
    analyst_headers = _add_member_with_role(client, owner_headers, org_id, "analyst")

    resp = client.post("/api/v1/seo/generate", json={"topic": "test"}, headers=analyst_headers)
    assert resp.status_code == 403
