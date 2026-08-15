"""
Dashboard summary endpoint.

Every field is either real queried data (business name, marketing goal,
budget, connected platform count) or a hardcoded empty state with a clear
comment on why (campaign/content/leads/sales/spend — no backing tables
exist yet). See app/schemas/dashboard.py for the field-by-field rationale.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_org_member
from app.db.session import get_db
from app.models.connected_account import ConnectedAccount, ConnectionStatus
from app.models.organization import Organization, OrganizationMember
from app.onboarding.service import get_or_create_business_profile
from app.schemas.dashboard import DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    org = db.get(Organization, member.organization_id)
    profile = get_or_create_business_profile(db, member.organization_id)

    connected_platforms_count = (
        db.query(ConnectedAccount)
        .filter(
            ConnectedAccount.organization_id == member.organization_id,
            ConnectedAccount.status == ConnectionStatus.CONNECTED,
        )
        .count()
    )

    return DashboardSummary(
        business_name=org.name,
        marketing_goal=profile.marketing_goal.value if profile.marketing_goal else None,
        monthly_ad_budget=profile.monthly_ad_budget,
        budget_currency=profile.budget_currency,
        connected_platforms_count=connected_platforms_count,
        onboarding_completed=profile.onboarding_completed_at is not None,
    )
