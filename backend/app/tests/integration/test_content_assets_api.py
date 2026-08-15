"""
Integration tests for /api/v1/content-assets/*. Mocks both boto3 (S3) and
the vision provider so no real network calls happen.
"""
from unittest.mock import MagicMock, patch

import httpx

from app.ai_providers.claude_provider import ClaudeProvider
from app.core.config import settings
from app.tests.conftest import unique_email


def _configure_s3(monkeypatch):
    """S3 config is unset by default in the test environment (see
    app/storage/client.py::_get_client, which correctly raises
    StorageNotConfiguredError when it's missing — verified behavior, not
    a gap). Patching settings directly here — the same pattern used for
    ANTHROPIC_API_KEY in other integration tests — rather than relying on
    environment variables, which aren't guaranteed to be set when the
    full suite runs."""
    monkeypatch.setattr(settings, "S3_ACCESS_KEY_ID", "test-key-id")
    monkeypatch.setattr(settings, "S3_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setattr(settings, "S3_BUCKET_NAME", "test-bucket")


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


def _vision_provider(description: str):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": description}],
                "usage": {"input_tokens": 100, "output_tokens": 20},
            },
        )

    return ClaudeProvider(api_key="test-key", transport=httpx.MockTransport(handler))


def test_upload_image_asset_full_flow(client, seeded_roles, monkeypatch):
    _configure_s3(monkeypatch)
    monkeypatch.setattr(
        "app.content.asset_service.get_ai_provider_for_task",
        lambda task: _vision_provider("A lit lavender candle on a wooden table"),
    )
    headers = _register_and_org_headers(client)

    with patch("boto3.client") as mock_boto:
        mock_s3_client = MagicMock()
        mock_s3_client.generate_presigned_url.return_value = "https://fake-presigned-url.example.com/asset.jpg"
        mock_boto.return_value = mock_s3_client
        resp = client.post(
            "/api/v1/content-assets",
            files={"file": ("candle.jpg", b"\xff\xd8\xff" + b"fakejpegdata", "image/jpeg")},
            headers=headers,
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "analyzed"
    assert body["ai_description"] == "A lit lavender candle on a wooden table"
    assert body["asset_type"] == "image"


def test_upload_asset_requires_can_manage_content(client, seeded_roles):
    owner_headers = _register_and_org_headers(client)
    org_id = owner_headers["X-Organization-Id"]
    analyst_headers = _add_member_with_role(client, owner_headers, org_id, "analyst")

    with patch("boto3.client") as mock_boto:
        mock_s3_client = MagicMock()
        mock_s3_client.generate_presigned_url.return_value = "https://fake-presigned-url.example.com/asset.jpg"
        mock_boto.return_value = mock_s3_client
        resp = client.post(
            "/api/v1/content-assets",
            files={"file": ("x.jpg", b"fakejpeg", "image/jpeg")},
            headers=analyst_headers,
        )
    assert resp.status_code == 403


def test_upload_asset_rejects_unsupported_type(client, seeded_roles):
    headers = _register_and_org_headers(client)
    with patch("boto3.client") as mock_boto:
        mock_s3_client = MagicMock()
        mock_s3_client.generate_presigned_url.return_value = "https://fake-presigned-url.example.com/asset.jpg"
        mock_boto.return_value = mock_s3_client
        resp = client.post(
            "/api/v1/content-assets",
            files={"file": ("doc.pdf", b"fakepdf", "application/pdf")},
            headers=headers,
        )
    assert resp.status_code == 400


def test_list_and_get_assets(client, seeded_roles, monkeypatch):
    _configure_s3(monkeypatch)
    monkeypatch.setattr(
        "app.content.asset_service.get_ai_provider_for_task",
        lambda task: _vision_provider("A candle"),
    )
    headers = _register_and_org_headers(client)

    with patch("boto3.client") as mock_boto:
        mock_s3_client = MagicMock()
        mock_s3_client.generate_presigned_url.return_value = "https://fake-presigned-url.example.com/asset.jpg"
        mock_boto.return_value = mock_s3_client
        upload_resp = client.post(
            "/api/v1/content-assets",
            files={"file": ("candle.jpg", b"fakejpeg", "image/jpeg")},
            headers=headers,
        )
        asset_id = upload_resp.json()["id"]

        list_resp = client.get("/api/v1/content-assets", headers=headers)
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1

        get_resp = client.get(f"/api/v1/content-assets/{asset_id}", headers=headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == asset_id


def test_assets_isolated_across_organizations(client, seeded_roles, monkeypatch):
    _configure_s3(monkeypatch)
    monkeypatch.setattr(
        "app.content.asset_service.get_ai_provider_for_task",
        lambda task: _vision_provider("A candle"),
    )
    org_a_headers = _register_and_org_headers(client)
    org_b_headers = _register_and_org_headers(client)

    with patch("boto3.client") as mock_boto:
        mock_s3_client = MagicMock()
        mock_s3_client.generate_presigned_url.return_value = "https://fake-presigned-url.example.com/asset.jpg"
        mock_boto.return_value = mock_s3_client
        upload_resp = client.post(
            "/api/v1/content-assets",
            files={"file": ("candle.jpg", b"fakejpeg", "image/jpeg")},
            headers=org_a_headers,
        )
    asset_id = upload_resp.json()["id"]

    resp = client.get(f"/api/v1/content-assets/{asset_id}", headers=org_b_headers)
    assert resp.status_code == 404


def test_delete_asset(client, seeded_roles, monkeypatch):
    _configure_s3(monkeypatch)
    monkeypatch.setattr(
        "app.content.asset_service.get_ai_provider_for_task",
        lambda task: _vision_provider("A candle"),
    )
    headers = _register_and_org_headers(client)

    with patch("boto3.client") as mock_boto:
        mock_s3_client = MagicMock()
        mock_s3_client.generate_presigned_url.return_value = "https://fake-presigned-url.example.com/asset.jpg"
        mock_boto.return_value = mock_s3_client
        upload_resp = client.post(
            "/api/v1/content-assets",
            files={"file": ("candle.jpg", b"fakejpeg", "image/jpeg")},
            headers=headers,
        )
        asset_id = upload_resp.json()["id"]

        delete_resp = client.delete(f"/api/v1/content-assets/{asset_id}", headers=headers)
        assert delete_resp.status_code == 200

        get_resp = client.get(f"/api/v1/content-assets/{asset_id}", headers=headers)
        assert get_resp.status_code == 404
