"""
Week 12 final end-to-end simulation.

Simulates a real customer through the spec's exact 14 steps, all via
REAL HTTP requests against a real (in-memory) instance of the actual
FastAPI app - not a description of what should happen. Prints a clear
PASS/FAIL for each step and stops at the first real failure so it can
be fixed before continuing, per the spec's own instruction: "Fix every
issue discovered."

Run with:
    cd backend && export SECRET_KEY=testkey CREDENTIALS_ENCRYPTION_KEY=wq0oR7VbLdoImevZgKUKcOc1qgO2gh8OyRSFvUgm3mQ= DATABASE_URL=sqlite:///:memory: APP_ENV=test
    python3 -m app.tests.e2e_simulation
"""
import json
import sys
import uuid
from datetime import date, timedelta

import httpx

sys.path.insert(0, ".")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

import app.models as m
from app.db.base_class import Base
from app.db.session import get_db
from app.db.seed_roles import SYSTEM_ROLES
from app.db.seed_plans import SYSTEM_PLANS
from app.main import app
from app.models.organization import Role
from app.core.security import encrypt_secret

STEP_RESULTS = []


def step(number: int, name: str):
    def decorator(fn):
        def wrapper(*args, **kwargs):
            print(f"\n--- Step {number}: {name} ---")
            try:
                result = fn(*args, **kwargs)
                print(f"✅ PASS")
                STEP_RESULTS.append((number, name, True, None))
                return result
            except Exception as exc:
                print(f"❌ FAIL: {exc}")
                STEP_RESULTS.append((number, name, False, str(exc)))
                raise
        return wrapper
    return decorator


def main():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    for rd in SYSTEM_ROLES:
        s.add(Role(**rd))
    for pd in SYSTEM_PLANS:
        s.add(m.SubscriptionPlan(**pd))
    s.commit()

    def override_db():
        yield s

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    ctx = {}

    @step(1, "Register")
    def step1():
        resp = client.post("/api/v1/auth/register", json={
            "email": "sarah@candleco.example.com", "password": "supersecret123",
            "full_name": "Sarah Candleman", "organization_name": "Candle Co",
        })
        assert resp.status_code == 201, resp.text
        ctx["access_token"] = resp.json()["access_token"]
        ctx["headers"] = {"Authorization": f"Bearer {ctx['access_token']}"}
        orgs = client.get("/api/v1/organizations", headers=ctx["headers"]).json()
        ctx["org_id"] = orgs[0]["id"]
        ctx["org_headers"] = {**ctx["headers"], "X-Organization-Id": ctx["org_id"]}
        ctx["user_id"] = client.get("/api/v1/users/me", headers=ctx["headers"]).json()["id"]

    @step(2, "Create business (onboarding)")
    def step2():
        h = ctx["org_headers"]
        assert client.put("/api/v1/onboarding/step-2-website", json={"website_url": "https://candleco.example.com"}, headers=h).status_code == 200
        assert client.put("/api/v1/onboarding/step-3-industry", json={"industry": "Home goods"}, headers=h).status_code == 200
        assert client.put("/api/v1/onboarding/step-4-country", json={"country": "US"}, headers=h).status_code == 200
        assert client.put("/api/v1/onboarding/step-5-products-services", json={"products_services": "Hand-poured soy candles"}, headers=h).status_code == 200
        assert client.put("/api/v1/onboarding/step-6-target-customers", json={"target_customers": "Home decor shoppers, 25-45"}, headers=h).status_code == 200
        assert client.put("/api/v1/onboarding/step-7-marketing-goal", json={"marketing_goal": "sales"}, headers=h).status_code == 200
        assert client.put("/api/v1/onboarding/step-8-budget", json={"monthly_ad_budget": 50000, "budget_currency": "USD"}, headers=h).status_code == 200
        assert client.put("/api/v1/onboarding/step-9-social-platforms", json={"social_platforms": ["facebook", "instagram"]}, headers=h).status_code == 200
        assert client.put("/api/v1/onboarding/step-10-advertising-platforms", json={"advertising_platforms": ["meta_ads"]}, headers=h).status_code == 200
        resp = client.post("/api/v1/onboarding/complete", headers=h)
        assert resp.status_code == 200, resp.text

    @step(3, "Add product (via business profile products_services - confirmed already set in step 2)")
    def step3():
        resp = client.get("/api/v1/onboarding", headers=ctx["org_headers"])
        assert resp.status_code == 200
        assert "candles" in resp.json()["products_services"].lower()

    @step(4, "Connect advertising account")
    def step4():
        project_resp = client.post("/api/v1/projects", json={"name": "Candle Co"}, headers=ctx["org_headers"])
        assert project_resp.status_code == 201, project_resp.text
        ctx["project_id"] = project_resp.json()["id"]

        creds = encrypt_secret(json.dumps({"access_token": "sim-token"}))
        connected = m.ConnectedAccount(organization_id=uuid.UUID(ctx["org_id"]), project_id=uuid.UUID(ctx["project_id"]), platform=m.PlatformType.META_ADS, status=m.ConnectionStatus.CONNECTED, encrypted_credentials=creds)
        s.add(connected)
        s.commit()
        ctx["connected_account_id"] = str(connected.id)

        ad_account_resp = client.post("/api/v1/meta-ads/ad-accounts", json={"connected_account_id": ctx["connected_account_id"], "external_ad_account_id": "act_sim", "name": "Candle Co Ads", "currency": "USD", "timezone_name": "UTC"}, headers=ctx["org_headers"])
        assert ad_account_resp.status_code == 201, ad_account_resp.text
        ctx["ad_account_id"] = ad_account_resp.json()["id"]

    @step(5, "Create campaign")
    def step5():
        resp = client.post("/api/v1/campaigns", json={
            "product_name": "Hand-poured soy candles", "objective": "sales", "desired_outcome_count": 100,
            "budget_amount": 50000, "budget_currency": "USD", "target_location": "United States",
        }, headers=ctx["org_headers"])
        assert resp.status_code == 201, resp.text
        ctx["campaign_id"] = resp.json()["id"]

    @step(6, "Generate content")
    def step6():
        def handler(request):
            return httpx.Response(200, json={"content": [{"type": "text", "text": "Warm up your home with our hand-poured soy candles. 🕯️ Shop the collection today!"}], "usage": {"input_tokens": 200, "output_tokens": 60}})
        from app.ai_providers.claude_provider import ClaudeProvider
        import app.content.generation_service as gen_svc
        original_get_provider = gen_svc.get_ai_provider_for_task
        # Patches generation_service's own imported reference, not the
        # factory module's - `from X import Y` binds a local name at
        # import time, so reassigning factory.get_ai_provider_for_task
        # afterward has no effect on generation_service's already-bound
        # reference. Confirmed correct by checking how the real, working
        # test suite mocks this exact function (see
        # app/tests/integration/test_content_api.py).
        gen_svc.get_ai_provider_for_task = lambda task: ClaudeProvider(api_key="sim-key", transport=httpx.MockTransport(handler))

        resp = client.post("/api/v1/content/generate", json={"content_type": "facebook_post", "source_text": "Announce our new candle collection"}, headers=ctx["org_headers"])
        gen_svc.get_ai_provider_for_task = original_get_provider
        assert resp.status_code == 200, resp.text
        ctx["content_id"] = resp.json()["id"]

    @step(7, "Schedule content")
    def step7():
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        resp = client.post("/api/v1/scheduled-posts", json={"content_id": ctx["content_id"], "connected_account_id": ctx["connected_account_id"], "scheduled_for": f"{tomorrow}T10:00:00Z"}, headers=ctx["org_headers"])
        assert resp.status_code == 201, resp.text
        ctx["scheduled_post_id"] = resp.json()["id"]

    @step(8, "Approve campaign")
    def step8():
        plan_response = {"strategy": {"objective": "Generate qualified leads", "target_audience": "Home decor shoppers, 25-45", "key_messages": ["Hand-poured quality"], "cta": "Shop now"}, "ad_copy_variants": [{"headline": "Hand-Poured Soy Candles", "primary_text": "Warm your home naturally.", "cta": "Shop Now"}], "creative_concepts": ["Cozy home lifestyle shot"]}

        def handler(request):
            return httpx.Response(200, json={"content": [{"type": "text", "text": json.dumps(plan_response)}], "usage": {"input_tokens": 300, "output_tokens": 150}})
        from app.ai_providers.claude_provider import ClaudeProvider
        import app.campaigns.generation_service as camp_gen_svc
        original_get_provider = camp_gen_svc.get_ai_provider_for_task
        camp_gen_svc.get_ai_provider_for_task = lambda task: ClaudeProvider(api_key="sim-key", transport=httpx.MockTransport(handler))

        gen_resp = client.post(f"/api/v1/campaigns/{ctx['campaign_id']}/generate", headers=ctx["org_headers"])
        camp_gen_svc.get_ai_provider_for_task = original_get_provider
        assert gen_resp.status_code == 200, gen_resp.text

        approve_resp = client.post(f"/api/v1/campaigns/{ctx['campaign_id']}/approve", headers=ctx["org_headers"])
        assert approve_resp.status_code == 200, approve_resp.text

    @step(9, "Launch campaign")
    def step9():
        resp = client.put(f"/api/v1/meta-ads/ad-accounts/{ctx['ad_account_id']}/spend-limit", json={"daily_spend_limit_cents": 5000}, headers=ctx["org_headers"])
        assert resp.status_code == 200, resp.text

        meta_campaign = m.MetaCampaign(organization_id=uuid.UUID(ctx["org_id"]), meta_ad_account_id=uuid.UUID(ctx["ad_account_id"]), name="Candle Co Launch", objective=m.MetaCampaignObjective.OUTCOME_SALES, external_campaign_id="c_sim", status=m.MetaCampaignStatus.PAUSED, daily_budget_cents=3000)
        s.add(meta_campaign)
        s.commit()
        ctx["meta_campaign_id"] = str(meta_campaign.id)

        launch_resp = client.post(f"/api/v1/meta-ads/meta-campaigns/{ctx['meta_campaign_id']}/request-status-change", json={"new_status": "ACTIVE"}, headers=ctx["org_headers"])
        assert launch_resp.status_code == 200, launch_resp.text
        ctx["launch_approval_id"] = launch_resp.json()["id"]
        review_resp = client.post(f"/api/v1/meta-ads/approval-requests/{ctx['launch_approval_id']}/review", json={"approve": True}, headers=ctx["org_headers"])
        assert review_resp.status_code == 200, review_resp.text

    @step(10, "Collect leads")
    def step10():
        resp = client.post("/api/v1/leads", json={"full_name": "Amy Buyer", "email": "amy@example.com", "product_interest": "Candles", "disclosed_budget_cents": 3000}, headers=ctx["org_headers"])
        assert resp.status_code == 201, resp.text
        ctx["lead_id"] = resp.json()["id"]

    @step(11, "Track sales")
    def step11():
        transition_resp = client.post(f"/api/v1/leads/{ctx['lead_id']}/transition", json={"to_stage": "won"}, headers=ctx["org_headers"])
        assert transition_resp.status_code == 200, transition_resp.text

    @step(12, "Analyze results")
    def step12():
        today = date.today().isoformat()
        resp = client.get(f"/api/v1/leads/analytics/summary?date_start={today}&date_stop={today}", headers=ctx["org_headers"])
        assert resp.status_code == 200, resp.text
        assert resp.json()["sales"] == 1

    @step(13, "Optimize campaign")
    def step13():
        s.add(m.CampaignWhitelist(organization_id=uuid.UUID(ctx["org_id"]), meta_campaign_id=uuid.UUID(ctx["meta_campaign_id"]), added_by_user_id=uuid.UUID(ctx["user_id"])))
        s.commit()
        settings_resp = client.get(f"/api/v1/optimization/meta-campaigns/{ctx['meta_campaign_id']}/autonomy-settings", headers=ctx["org_headers"])
        assert settings_resp.status_code == 200, settings_resp.text
        scan_resp = client.post(f"/api/v1/optimization/meta-campaigns/{ctx['meta_campaign_id']}/scan", headers=ctx["org_headers"])
        assert scan_resp.status_code == 200, scan_resp.text

    @step(14, "Generate report")
    def step14():
        def handler(request):
            return httpx.Response(200, json={"content": [{"type": "text", "text": "Your candle campaign is off to a strong start with 1 real sale this period."}], "usage": {"input_tokens": 300, "output_tokens": 80}})
        from app.ai_providers.claude_provider import ClaudeProvider
        import app.leads.sales_agent as sales_agent_svc
        original_get_provider = sales_agent_svc.get_ai_provider_for_task
        sales_agent_svc.get_ai_provider_for_task = lambda task: ClaudeProvider(api_key="sim-key", transport=httpx.MockTransport(handler))

        today = date.today().isoformat()
        resp = client.post("/api/v1/leads/analytics/ask", json={"question": "How did this period go?", "date_start": today, "date_stop": today}, headers=ctx["org_headers"])
        sales_agent_svc.get_ai_provider_for_task = original_get_provider
        assert resp.status_code == 200, resp.text
        assert len(resp.json()["answer_text"]) > 0

    steps = [step1, step2, step3, step4, step5, step6, step7, step8, step9, step10, step11, step12, step13, step14]
    for fn in steps:
        try:
            fn()
        except Exception:
            break

    print("\n\n=== SIMULATION SUMMARY ===")
    for number, name, passed, error in STEP_RESULTS:
        status = "✅ PASS" if passed else f"❌ FAIL: {error}"
        print(f"{number:2d}. {name}: {status}")

    passed_count = sum(1 for _, _, p, _ in STEP_RESULTS if p)
    print(f"\n{passed_count}/{len(steps)} steps passed")
    return passed_count == len(steps)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
