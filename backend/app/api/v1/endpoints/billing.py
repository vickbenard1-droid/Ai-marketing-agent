"""
Billing endpoints: real subscription plans, an organization's current
plan + real usage, and changing plans (gated by can_manage_billing -
only 'owner' has this by default, see app/db/seed_roles.py).

Deliberately does NOT include actual payment processing (charging a
card, a Stripe/payment-provider integration) - the spec asks for a
subscription SYSTEM (tiers, limits, tracking), not live payment
collection, and building a half-tested real-money integration this late
in a hardening-focused week would be a worse outcome than a clean,
correct plan-selection layer with real usage enforcement and an honest
gap noted for the final report.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_org_member, require_permission
from app.billing.service import get_plan_for_organization, get_usage_snapshot
from app.db.session import get_db
from app.models.organization import Organization, OrganizationMember
from app.models.subscription_plan import SubscriptionPlan
from app.schemas.billing import ChangePlanRequest, CurrentPlanAndUsagePublic, SubscriptionPlanPublic, UsageCategoryPublic

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/plans", response_model=list[SubscriptionPlanPublic])
def list_plans(db: Session = Depends(get_db)):
    """Public within the app (any authenticated context isn't even
    required) - a person choosing a plan needs to see the real options
    and prices before committing to anything."""
    return db.query(SubscriptionPlan).filter(SubscriptionPlan.is_active.is_(True)).order_by(SubscriptionPlan.monthly_price_cents).all()


@router.get("/current", response_model=CurrentPlanAndUsagePublic)
def get_current_plan_and_usage(member: OrganizationMember = Depends(get_current_org_member), db: Session = Depends(get_db)):
    plan = get_plan_for_organization(db, member.organization_id)
    usage = get_usage_snapshot(db, member.organization_id)
    return CurrentPlanAndUsagePublic(
        plan=SubscriptionPlanPublic.model_validate(plan),
        usage=[UsageCategoryPublic(category=u.category, current=u.current, limit=u.limit) for u in usage],
    )


@router.post("/change-plan", response_model=SubscriptionPlanPublic)
def change_plan(
    payload: ChangePlanRequest,
    member: OrganizationMember = Depends(require_permission("can_manage_billing")),
    db: Session = Depends(get_db),
):
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.name == payload.plan_name, SubscriptionPlan.is_active.is_(True)).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No active plan named '{payload.plan_name}'")

    org = db.get(Organization, member.organization_id)
    org.subscription_plan_id = plan.id
    db.commit()
    db.refresh(plan)
    return plan
