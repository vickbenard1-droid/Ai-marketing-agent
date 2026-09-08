"""
Tests for the public, unauthenticated /api/v1/track/* endpoints.

Includes a regression test for a real data-integrity gap found during
the Week 12 security audit: conversion_value_cents had no bounds at
all, and this endpoint is deliberately public (the tracking key is
meant to be embedded in a business's own public page source) - a leaked
or guessed key could otherwise be used to submit an arbitrarily large
or negative fake conversion value, corrupting real revenue/ROAS figures
this organization's own sales and optimization agents reason over.
"""
from app.tests.conftest import unique_email


def _register_org_and_get_tracking_key(client):
    email = unique_email()
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "supersecret123", "full_name": "Test User", "organization_name": f"Org {email}"},
    )
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    org_id = client.get("/api/v1/organizations", headers=headers).json()[0]["id"]
    org_headers = {**headers, "X-Organization-Id": org_id}
    tracking_key = client.get("/api/v1/analytics/tracking-key", headers=org_headers).json()["key"]
    return org_headers, tracking_key


def test_track_page_view_with_real_key_succeeds(client, seeded_roles):
    _, tracking_key = _register_org_and_get_tracking_key(client)
    resp = client.post("/api/v1/track/page-view", json={"tracking_key": tracking_key, "visitor_id": "v1", "page_url": "/pricing"})
    assert resp.status_code == 204


def test_track_page_view_with_unknown_key_is_rejected(client, seeded_roles):
    resp = client.post("/api/v1/track/page-view", json={"tracking_key": "not_a_real_key", "visitor_id": "v1"})
    assert resp.status_code == 404


def test_track_conversion_with_legitimate_value_succeeds(client, seeded_roles):
    _, tracking_key = _register_org_and_get_tracking_key(client)
    resp = client.post("/api/v1/track/conversion", json={"tracking_key": tracking_key, "visitor_id": "v1", "conversion_type_name": "Sale", "conversion_value_cents": 15000})
    assert resp.status_code == 204


def test_track_conversion_rejects_negative_value(client, seeded_roles):
    """Regression test for the fixed vulnerability: a leaked/guessed
    tracking key could previously be used to submit a fabricated
    negative conversion value with no bound at all."""
    _, tracking_key = _register_org_and_get_tracking_key(client)
    resp = client.post("/api/v1/track/conversion", json={"tracking_key": tracking_key, "visitor_id": "v1", "conversion_type_name": "Sale", "conversion_value_cents": -500})
    assert resp.status_code == 422


def test_track_conversion_rejects_absurd_value(client, seeded_roles):
    """Regression test for the same fix - an unbounded value could
    previously be used to inject an absurd fake conversion (e.g. to
    poison an org's own ROAS/optimization decisions)."""
    _, tracking_key = _register_org_and_get_tracking_key(client)
    resp = client.post("/api/v1/track/conversion", json={"tracking_key": tracking_key, "visitor_id": "v1", "conversion_type_name": "Sale", "conversion_value_cents": 99999999999})
    assert resp.status_code == 422
