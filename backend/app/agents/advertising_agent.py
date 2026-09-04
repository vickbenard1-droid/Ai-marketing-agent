"""
Advertising Agent.

CRITICAL: this agent NEVER calls execute_campaign_status_change() or
execute_budget_change() directly - only the request_*() functions,
which create a PENDING ApprovalRequest and make zero real API calls.
Actual execution stays behind Week 7's separate, explicit human review
step (app.meta_ads.execution_service.execute_*, still gated by the
spend guard) regardless of how this agent is invoked - the orchestrator
cannot approve its own advertising spend requests.
"""
import uuid

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.meta_ads.execution_service import ExecutionServiceError, request_budget_change, request_campaign_status_change


class AdvertisingAgent(BaseAgent):
    name = "advertising_agent"
    description = "Proposes Meta Ads campaign launches/budget changes as PENDING approval requests - never executes spend directly."

    def run(self, context: AgentContext, *, meta_campaign_id: str | None = None, new_status: str | None = None, new_daily_budget_cents: int | None = None, **kwargs) -> AgentResult:
        if not meta_campaign_id:
            return AgentResult(success=False, output=None, notes="No meta_campaign_id provided - the Advertising Agent needs a specific campaign to act on.")
        try:
            if new_daily_budget_cents is not None:
                approval = request_budget_change(context.db, organization_id=context.organization_id, requested_by_user_id=context.actor_user_id, meta_campaign_id=uuid.UUID(meta_campaign_id), new_daily_budget_cents=new_daily_budget_cents)
            elif new_status is not None:
                approval = request_campaign_status_change(context.db, organization_id=context.organization_id, requested_by_user_id=context.actor_user_id, meta_campaign_id=uuid.UUID(meta_campaign_id), new_status=new_status)
            else:
                return AgentResult(success=False, output=None, notes="Neither new_status nor new_daily_budget_cents provided.")
        except ExecutionServiceError as exc:
            return AgentResult(success=False, output=None, notes=str(exc))

        return AgentResult(success=True, output={"approval_request_id": str(approval.id), "status": approval.status.value}, requires_human_approval=True, notes="Created a PENDING approval request - no spend has occurred.")
