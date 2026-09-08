"""
Functional tests for /api/v1/leads/* - the Week 10 lead pipeline.
Complements app/tests/integration/test_meta_ads_isolation_api.py-style
security tests (there are none specific to leads yet, but the same
org-scoping discipline applies here too) by covering the actual
day-to-day workflow: create, transition, assign, note, qualify.
"""
from app.tests.conftest import unique_email


def _register_org(client):
    email = unique_email()
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "supersecret123", "full_name": "Test User", "organization_name": f"Org {email}"},
    )
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    org_id = client.get("/api/v1/organizations", headers=headers).json()[0]["id"]
    return {**headers, "X-Organization-Id": org_id}


def test_create_manual_lead_and_get_it(client, seeded_roles):
    org_headers = _register_org(client)
    create_resp = client.post("/api/v1/leads", json={"full_name": "Jane Doe", "email": "jane@example.com", "product_interest": "Candle set", "disclosed_budget_cents": 8000}, headers=org_headers)
    assert create_resp.status_code == 201
    lead = create_resp.json()
    assert lead["full_name"] == "Jane Doe"
    assert lead["stage"] == "new_lead"
    assert lead["score"] is not None  # real score computed on creation

    get_resp = client.get(f"/api/v1/leads/{lead['id']}", headers=org_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == lead["id"]


def test_create_lead_with_no_contact_info_is_rejected(client, seeded_roles):
    org_headers = _register_org(client)
    resp = client.post("/api/v1/leads", json={"product_interest": "Something"}, headers=org_headers)
    assert resp.status_code == 400


def test_list_leads_and_filter_by_stage(client, seeded_roles):
    org_headers = _register_org(client)
    client.post("/api/v1/leads", json={"email": "a@example.com"}, headers=org_headers)
    client.post("/api/v1/leads", json={"email": "b@example.com"}, headers=org_headers)

    all_leads = client.get("/api/v1/leads", headers=org_headers).json()
    assert len(all_leads) == 2

    new_stage_leads = client.get("/api/v1/leads?stage=new_lead", headers=org_headers).json()
    assert len(new_stage_leads) == 2

    won_leads = client.get("/api/v1/leads?stage=won", headers=org_headers).json()
    assert len(won_leads) == 0


def test_transition_lead_stage_records_history(client, seeded_roles):
    org_headers = _register_org(client)
    lead = client.post("/api/v1/leads", json={"email": "c@example.com"}, headers=org_headers).json()

    trans_resp = client.post(f"/api/v1/leads/{lead['id']}/transition", json={"to_stage": "contacted", "note": "Called them"}, headers=org_headers)
    assert trans_resp.status_code == 200
    assert trans_resp.json()["stage"] == "contacted"

    history_resp = client.get(f"/api/v1/leads/{lead['id']}/transitions", headers=org_headers)
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert len(history) == 2  # initial creation + the transition just made
    assert history[-1]["to_stage"] == "contacted"
    assert history[-1]["note"] == "Called them"


def test_update_lead_notes(client, seeded_roles):
    org_headers = _register_org(client)
    lead = client.post("/api/v1/leads", json={"email": "d@example.com"}, headers=org_headers).json()
    resp = client.post(f"/api/v1/leads/{lead['id']}/notes", json={"notes": "Interested in bulk pricing"}, headers=org_headers)
    assert resp.status_code == 200
    assert resp.json()["notes"] == "Interested in bulk pricing"


def test_qualification_criteria_default_and_update(client, seeded_roles):
    org_headers = _register_org(client)
    default_resp = client.get("/api/v1/leads/qualification/criteria", headers=org_headers)
    assert default_resp.status_code == 200
    assert default_resp.json()["minimum_score"] == 40

    update_resp = client.put("/api/v1/leads/qualification/criteria", json={"minimum_score": 60, "require_product_interest": True}, headers=org_headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["minimum_score"] == 60
    assert update_resp.json()["require_product_interest"] is True


def test_evaluate_and_commit_qualification(client, seeded_roles):
    org_headers = _register_org(client)
    lead = client.post("/api/v1/leads", json={"email": "e@example.com", "product_interest": "Candles", "disclosed_budget_cents": 5000}, headers=org_headers).json()

    eval_resp = client.get(f"/api/v1/leads/{lead['id']}/qualification", headers=org_headers)
    assert eval_resp.status_code == 200
    assert "qualifies" in eval_resp.json()
    assert "reasons" in eval_resp.json()

    qualify_resp = client.post(f"/api/v1/leads/{lead['id']}/qualify", headers=org_headers)
    assert qualify_resp.status_code == 200
    assert qualify_resp.json()["stage"] == "qualified"


def test_sales_analytics_summary_reflects_real_leads(client, seeded_roles):
    import datetime
    org_headers = _register_org(client)
    client.post("/api/v1/leads", json={"email": "f@example.com"}, headers=org_headers)
    today = datetime.date.today().isoformat()

    resp = client.get(f"/api/v1/leads/analytics/summary?date_start={today}&date_stop={today}", headers=org_headers)
    assert resp.status_code == 200
    assert resp.json()["leads"] == 1


def test_leads_are_isolated_across_organizations(client, seeded_roles):
    org_a_headers = _register_org(client)
    org_b_headers = _register_org(client)

    lead = client.post("/api/v1/leads", json={"email": "secret@example.com"}, headers=org_a_headers).json()

    cross_org_resp = client.get(f"/api/v1/leads/{lead['id']}", headers=org_b_headers)
    assert cross_org_resp.status_code == 404

    org_b_list = client.get("/api/v1/leads", headers=org_b_headers).json()
    assert len(org_b_list) == 0
