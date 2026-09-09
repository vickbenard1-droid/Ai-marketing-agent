"""
Seeds the 4 system subscription plans the spec asks for: Free, Starter,
Professional, Agency.

Real, reasoned limits, not arbitrary placeholders - each tier's limits
scale with what that tier's real price point should support, and Agency
is genuinely unlimited (None) across every category, matching the spec's
framing of Agency as the tier for managing multiple clients at scale
rather than a fixed usage ceiling.

Run with: python -m app.db.seed_plans
Idempotent - safe to run multiple times (upserts by name), same pattern
as app.db.seed_roles.
"""
from app.db.session import SessionLocal
from app.models.subscription_plan import SubscriptionPlan

SYSTEM_PLANS = [
    {
        "name": "free",
        "display_name": "Free",
        "monthly_price_cents": 0,
        "max_ai_tokens_per_month": 50_000,
        "max_campaigns": 1,
        "max_connected_accounts": 1,
        "max_content_generations_per_month": 10,
        "max_automated_actions_per_month": 0,
        "is_active": True,
    },
    {
        "name": "starter",
        "display_name": "Starter",
        "monthly_price_cents": 2900,
        "max_ai_tokens_per_month": 500_000,
        "max_campaigns": 5,
        "max_connected_accounts": 3,
        "max_content_generations_per_month": 100,
        "max_automated_actions_per_month": 20,
        "is_active": True,
    },
    {
        "name": "professional",
        "display_name": "Professional",
        "monthly_price_cents": 9900,
        "max_ai_tokens_per_month": 2_500_000,
        "max_campaigns": 25,
        "max_connected_accounts": 10,
        "max_content_generations_per_month": 500,
        "max_automated_actions_per_month": 200,
        "is_active": True,
    },
    {
        "name": "agency",
        "display_name": "Agency",
        "monthly_price_cents": 29900,
        "max_ai_tokens_per_month": None,
        "max_campaigns": None,
        "max_connected_accounts": None,
        "max_content_generations_per_month": None,
        "max_automated_actions_per_month": None,
        "is_active": True,
    },
]


def seed_plans() -> None:
    db = SessionLocal()
    try:
        for plan_data in SYSTEM_PLANS:
            existing = db.query(SubscriptionPlan).filter(SubscriptionPlan.name == plan_data["name"]).first()
            if existing:
                for key, value in plan_data.items():
                    setattr(existing, key, value)
            else:
                db.add(SubscriptionPlan(**plan_data))
        db.commit()
        print(f"Seeded {len(SYSTEM_PLANS)} subscription plans.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_plans()
