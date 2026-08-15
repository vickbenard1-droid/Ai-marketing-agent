"""
Agent endpoints.

Running an agent is gated on can_execute_ai_actions — the same permission
flag Week 2 already seeded onto every role (Viewer/Analyst don't have it,
Manager/Content Manager/Admin/Owner do — see app/db/seed_roles.py). Every
agent call incurs real AI provider cost, so this deliberately isn't gated
behind mere org membership the way read-only endpoints are.
"""
import app.agents  # noqa: F401 — import side effect registers all agents
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.base import AgentContext, agent_registry
from app.auth.dependencies import require_permission
from app.db.session import get_db
from app.models.organization import OrganizationMember
from app.schemas.agent import AgentInfo, RunAgentRequest, RunAgentResponse

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=list[AgentInfo])
def list_agents(
    member: OrganizationMember = Depends(require_permission("can_execute_ai_actions")),
):
    return [
        AgentInfo(name=name, description=agent_registry.get(name).description)
        for name in agent_registry.list_agents()
    ]


@router.post("/{agent_name}/run", response_model=RunAgentResponse)
def run_agent(
    agent_name: str,
    payload: RunAgentRequest,
    member: OrganizationMember = Depends(require_permission("can_execute_ai_actions")),
    db: Session = Depends(get_db),
):
    agent = agent_registry.get(agent_name)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No agent named '{agent_name}'. Available: {agent_registry.list_agents()}",
        )

    context = AgentContext(
        db=db, organization_id=member.organization_id, actor_user_id=member.user_id
    )
    result = agent.run(context, brief=payload.brief)
    db.commit()

    return RunAgentResponse(
        agent=agent_name,
        success=result.success,
        output=result.output,
        requires_human_approval=result.requires_human_approval,
        notes=result.notes,
    )
