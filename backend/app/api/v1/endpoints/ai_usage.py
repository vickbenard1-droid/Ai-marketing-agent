from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai_usage.service import get_usage_summary
from app.auth.dependencies import get_current_org_member
from app.db.session import get_db
from app.models.organization import OrganizationMember
from app.schemas.ai_usage import AIUsageSummary

router = APIRouter(prefix="/ai-usage", tags=["ai-usage"])


@router.get("/summary", response_model=AIUsageSummary)
def get_my_org_usage_summary(
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    """
    Any member can view usage/cost — not gated behind can_execute_ai_actions
    since seeing what's already been spent is a read concern, distinct
    from incurring new spend by running an agent or sending a chat message.
    """
    return get_usage_summary(db, member.organization_id)
