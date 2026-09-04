"""
Orchestrator service.

The core engine: create_run() plans a goal into an ordered sequence of
real agent steps (via app.agents.base.agent_registry - the planner is
structurally unable to invent an agent that doesn't exist, since the
prompt is given the exact registered agent names and any name outside
that set is rejected). advance_run() executes the plan one step at a
time, writing a real AgentActivityLog row for every step BEFORE and
AFTER running it (so a person watching the timeline sees the step
appear as in_progress, not just retroactively as completed), and PAUSES
before any step marked requires_approval=True rather than proceeding on
its own authority - the concrete mechanism behind "the user must remain
in control."
"""
import json
import uuid
from typing import Optional

from sqlalchemy.orm import Session

import app.agents  # noqa: F401 — registers every concrete agent
from app.agents.base import AgentContext, agent_registry
from app.ai_providers.base import AIMessage, AIProviderError, AITaskType
from app.ai_providers.factory import get_ai_provider_for_task
from app.ai_usage.service import generate_and_track
from app.knowledge.service import get_business_knowledge
from app.models.agent_activity_log import ActivityStatus, AgentActivityLog
from app.models.agent_decision import AgentDecision
from app.models.ai_usage_log import AIUsageSource
from app.models.orchestration_run import OrchestrationRun, OrchestrationRunStatus
from app.prompts.registry import ORCHESTRATOR_PLANNING_SYSTEM


class OrchestratorError(Exception):
    pass


def _available_agents_summary() -> list:
    return [{"agent_name": name, "description": agent_registry.get(name).description} for name in agent_registry.list_agents()]


def create_run(db: Session, *, organization_id: uuid.UUID, requested_by_user_id: Optional[uuid.UUID], goal_text: str) -> OrchestrationRun:
    """Plans the goal into an ordered step list via the AI, validating
    every step's agent_name against the real registry before accepting
    the plan - never trusts the AI's plan blindly."""
    knowledge = get_business_knowledge(db, organization_id)
    available_agents = _available_agents_summary()
    system = ORCHESTRATOR_PLANNING_SYSTEM.render_system(business_context=knowledge.render(), goal_text=goal_text, available_agents_json=json.dumps(available_agents))

    run = OrchestrationRun(organization_id=organization_id, requested_by_user_id=requested_by_user_id, goal_text=goal_text, status=OrchestrationRunStatus.PLANNING)
    db.add(run)
    db.commit()
    db.refresh(run)

    provider = get_ai_provider_for_task(AITaskType.ORCHESTRATOR_PLANNING)
    try:
        result = generate_and_track(db, provider, [AIMessage(role="user", content=f"Plan how to achieve this goal: {goal_text}")], organization_id=organization_id, actor_user_id=requested_by_user_id, source=AIUsageSource.ORCHESTRATOR_PLANNING, system=system, prompt_name=ORCHESTRATOR_PLANNING_SYSTEM.name, prompt_version=ORCHESTRATOR_PLANNING_SYSTEM.version, max_tokens=1500)
    except AIProviderError as exc:
        run.status = OrchestrationRunStatus.FAILED
        run.final_summary = f"Planning failed: {exc}"
        db.commit()
        raise OrchestratorError(f"AI planning request failed: {exc}") from exc

    from app.ai_utils.json_extraction import extract_json_object
    try:
        parsed = extract_json_object(result.text)
        raw_steps = parsed["steps"]
    except (ValueError, KeyError) as exc:
        run.status = OrchestrationRunStatus.FAILED
        run.final_summary = f"Planning produced an invalid response: {exc}"
        db.commit()
        raise OrchestratorError(f"AI planning response was invalid: {exc}") from exc

    known_agent_names = set(agent_registry.list_agents())
    validated_steps = []
    for raw_step in raw_steps:
        agent_name = raw_step.get("agent_name")
        if agent_name not in known_agent_names:
            continue  # silently drop a hallucinated agent name rather than fail the whole plan
        validated_steps.append({"agent_name": agent_name, "action_description": raw_step.get("action_description", ""), "requires_approval": bool(raw_step.get("requires_approval", False))})

    if not validated_steps:
        run.status = OrchestrationRunStatus.FAILED
        run.final_summary = "Planning did not produce any valid steps using real, registered agents."
        db.commit()
        raise OrchestratorError("No valid plan steps were generated")

    run.plan_json = validated_steps
    run.status = OrchestrationRunStatus.RUNNING
    run.final_summary = parsed.get("plan_summary")
    db.commit()
    db.refresh(run)
    return run


def _record_decision(db: Session, *, run: OrchestrationRun, agent_name: str, summary: str) -> None:
    db.add(AgentDecision(organization_id=run.organization_id, agent_name=agent_name, goal_description=run.goal_text, decision_summary=summary, context_json={"orchestration_run_id": str(run.id)}))


def advance_run(db: Session, *, organization_id: uuid.UUID, run: OrchestrationRun, actor_user_id: Optional[uuid.UUID] = None) -> OrchestrationRun:
    """
    Executes exactly ONE step of the plan, then returns. Never loops
    through multiple steps in one call - a step requiring approval must
    stop the run and wait for an explicit human action
    (app.orchestrator.service.approve_and_continue), and even a step
    that doesn't require approval only advances one step at a time so
    the activity log stays a genuine step-by-step trace a person can
    follow, not a black box that runs to completion silently.
    """
    if run.status != OrchestrationRunStatus.RUNNING:
        raise OrchestratorError(f"Run is not RUNNING (current status: {run.status.value})")
    if run.current_step >= len(run.plan_json):
        run.status = OrchestrationRunStatus.COMPLETED
        db.commit()
        return run

    step = run.plan_json[run.current_step]
    agent = agent_registry.get(step["agent_name"])
    if not agent:
        run.status = OrchestrationRunStatus.FAILED
        run.final_summary = f"Step referenced unknown agent '{step['agent_name']}'"
        db.commit()
        return run

    log = AgentActivityLog(organization_id=organization_id, orchestration_run_id=run.id, agent_name=step["agent_name"], step_number=run.current_step, action_description=step["action_description"], reasoning=f"Part of the plan for goal: {run.goal_text}", status=ActivityStatus.IN_PROGRESS, requires_approval=step["requires_approval"])
    db.add(log)
    db.commit()
    db.refresh(log)

    if step["requires_approval"]:
        log.status = ActivityStatus.AWAITING_APPROVAL
        run.status = OrchestrationRunStatus.PAUSED_FOR_APPROVAL
        db.commit()
        return run

    context = AgentContext(db=db, organization_id=organization_id, actor_user_id=actor_user_id)
    try:
        result = agent.run(context)
    except Exception as exc:
        log.status = ActivityStatus.FAILED
        log.execution_result_json = {"error": str(exc)}
        run.status = OrchestrationRunStatus.FAILED
        db.commit()
        return run

    log.status = ActivityStatus.COMPLETED if result.success else ActivityStatus.FAILED
    log.data_used_json = result.output if isinstance(result.output, dict) else {"output": str(result.output)}
    log.recommendation = result.notes
    log.execution_result_json = {"success": result.success}
    _record_decision(db, run=run, agent_name=step["agent_name"], summary=result.notes or step["action_description"])

    run.current_step += 1
    if run.current_step >= len(run.plan_json):
        run.status = OrchestrationRunStatus.COMPLETED
    db.commit()
    db.refresh(run)
    return run


def approve_step_and_continue(db: Session, *, organization_id: uuid.UUID, run: OrchestrationRun, actor_user_id: Optional[uuid.UUID], approve: bool, **agent_kwargs) -> OrchestrationRun:
    """The ONLY function that may advance a run past an
    AWAITING_APPROVAL step - a genuine, explicit human action is
    required; nothing in advance_run() can substitute for this call."""
    if run.status != OrchestrationRunStatus.PAUSED_FOR_APPROVAL:
        raise OrchestratorError(f"Run is not paused for approval (current status: {run.status.value})")

    log = db.query(AgentActivityLog).filter(AgentActivityLog.orchestration_run_id == run.id, AgentActivityLog.step_number == run.current_step).first()
    if not log:
        raise OrchestratorError("Could not find the activity log for the step awaiting approval")

    if not approve:
        log.status = ActivityStatus.REJECTED
        run.status = OrchestrationRunStatus.CANCELLED
        db.commit()
        return run

    log.status = ActivityStatus.APPROVED
    db.commit()

    step = run.plan_json[run.current_step]
    agent = agent_registry.get(step["agent_name"])
    context = AgentContext(db=db, organization_id=organization_id, actor_user_id=actor_user_id)
    try:
        result = agent.run(context, **agent_kwargs)
    except Exception as exc:
        log.status = ActivityStatus.FAILED
        log.execution_result_json = {"error": str(exc)}
        run.status = OrchestrationRunStatus.FAILED
        db.commit()
        return run

    log.status = ActivityStatus.COMPLETED if result.success else ActivityStatus.FAILED
    log.data_used_json = result.output if isinstance(result.output, dict) else {"output": str(result.output)}
    log.recommendation = result.notes
    log.execution_result_json = {"success": result.success}
    _record_decision(db, run=run, agent_name=step["agent_name"], summary=result.notes or step["action_description"])

    run.current_step += 1
    run.status = OrchestrationRunStatus.RUNNING if run.current_step < len(run.plan_json) else OrchestrationRunStatus.COMPLETED
    db.commit()
    db.refresh(run)
    return run
