"""
Orchestrator endpoints.

/orchestrator/agents lists the real registered agents (not a hardcoded
list) - what the frontend shows as "available agents" is always exactly
what the orchestrator itself can actually dispatch to.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

import app.agents  # noqa: F401 — registers every concrete agent
import app.orchestrator.memory as memory
import app.orchestrator.service as orch_service
from app.agents.base import agent_registry
from app.auth.dependencies import get_current_org_member, require_permission
from app.db.session import get_db
from app.models.agent_activity_log import AgentActivityLog
from app.models.agent_decision import AgentDecision
from app.models.orchestration_run import OrchestrationRun
from app.models.organization import OrganizationMember
from app.schemas.orchestrator import (
    AgentActivityLogPublic, AgentDecisionPublic, AgentSummaryPublic, ApproveStepRequest,
    CreateRunRequest, OrchestrationRunPublic, RelevantMemoryPublic,
)

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])


@router.get("/agents", response_model=list[AgentSummaryPublic])
def list_available_agents(member: OrganizationMember = Depends(get_current_org_member)):
    return [AgentSummaryPublic(name=name, description=agent_registry.get(name).description) for name in agent_registry.list_agents()]


@router.post("/runs", response_model=OrchestrationRunPublic, status_code=status.HTTP_201_CREATED)
def create_run(payload: CreateRunRequest, member: OrganizationMember = Depends(require_permission("can_execute_ai_actions")), db: Session = Depends(get_db)):
    try:
        return orch_service.create_run(db, organization_id=member.organization_id, requested_by_user_id=member.user_id, goal_text=payload.goal_text)
    except orch_service.OrchestratorError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/runs", response_model=list[OrchestrationRunPublic])
def list_runs(member: OrganizationMember = Depends(get_current_org_member), db: Session = Depends(get_db)):
    return db.query(OrchestrationRun).filter(OrchestrationRun.organization_id == member.organization_id).order_by(OrchestrationRun.created_at.desc()).all()


def _get_run_or_404(db: Session, organization_id: uuid.UUID, run_id: uuid.UUID) -> OrchestrationRun:
    run = db.query(OrchestrationRun).filter(OrchestrationRun.id == run_id, OrchestrationRun.organization_id == organization_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orchestration run not found")
    return run


@router.get("/runs/{run_id}", response_model=OrchestrationRunPublic)
def get_run(run_id: uuid.UUID, member: OrganizationMember = Depends(get_current_org_member), db: Session = Depends(get_db)):
    return _get_run_or_404(db, member.organization_id, run_id)


@router.post("/runs/{run_id}/advance", response_model=OrchestrationRunPublic)
def advance_run(run_id: uuid.UUID, member: OrganizationMember = Depends(require_permission("can_execute_ai_actions")), db: Session = Depends(get_db)):
    run = _get_run_or_404(db, member.organization_id, run_id)
    try:
        return orch_service.advance_run(db, organization_id=member.organization_id, run=run, actor_user_id=member.user_id)
    except orch_service.OrchestratorError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/runs/{run_id}/approve-step", response_model=OrchestrationRunPublic)
def approve_step(run_id: uuid.UUID, payload: ApproveStepRequest, member: OrganizationMember = Depends(require_permission("can_execute_ai_actions")), db: Session = Depends(get_db)):
    run = _get_run_or_404(db, member.organization_id, run_id)
    try:
        return orch_service.approve_step_and_continue(db, organization_id=member.organization_id, run=run, actor_user_id=member.user_id, approve=payload.approve, **payload.agent_kwargs)
    except orch_service.OrchestratorError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/runs/{run_id}/activity", response_model=list[AgentActivityLogPublic])
def get_run_activity(run_id: uuid.UUID, member: OrganizationMember = Depends(get_current_org_member), db: Session = Depends(get_db)):
    _get_run_or_404(db, member.organization_id, run_id)
    return db.query(AgentActivityLog).filter(AgentActivityLog.orchestration_run_id == run_id).order_by(AgentActivityLog.step_number).all()


@router.get("/activity", response_model=list[AgentActivityLogPublic])
def get_all_activity(limit: int = Query(default=50, le=200), member: OrganizationMember = Depends(get_current_org_member), db: Session = Depends(get_db)):
    """The full org-wide Agent Activity timeline, across every run - what the spec's observability section asks to be shown."""
    return db.query(AgentActivityLog).filter(AgentActivityLog.organization_id == member.organization_id).order_by(AgentActivityLog.created_at.desc()).limit(limit).all()


@router.get("/decisions", response_model=list[AgentDecisionPublic])
def list_decisions(agent_name: Optional[str] = Query(default=None), member: OrganizationMember = Depends(get_current_org_member), db: Session = Depends(get_db)):
    return memory.get_recent_decisions(db, member.organization_id, agent_name=agent_name, limit=50)


@router.get("/memory", response_model=RelevantMemoryPublic)
def get_memory(days: int = Query(default=30, ge=1, le=365), member: OrganizationMember = Depends(get_current_org_member), db: Session = Depends(get_db)):
    result = memory.get_relevant_memory(db, member.organization_id, days=days)
    return RelevantMemoryPublic(business_knowledge=result.business_knowledge, recent_performance=result.recent_performance, successful_strategies=result.successful_strategies, failed_strategies=result.failed_strategies, recent_customer_summary=result.recent_customer_summary)
