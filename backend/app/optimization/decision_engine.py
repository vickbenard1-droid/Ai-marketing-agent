"""
Decision engine.

Turns rules_engine.py's mechanical SignalEvaluation findings into full
OptimizationDecision rows - two-stage pipeline, deliberately:
rules_engine.py decides WHETHER something is worth a decision
(mechanical, testable in isolation); this module decides WHAT to
recommend and how to word it (AI-generated).

required_permission is mapped in code from a fixed table, never asked
of or trusted from the AI.
"""
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.ai_providers.base import AIMessage, AIProviderError, AITaskType
from app.ai_providers.factory import get_ai_provider_for_task
from app.ai_usage.service import generate_and_track
from app.ai_utils.json_extraction import extract_json_object
from app.models.ai_usage_log import AIUsageSource
from app.models.meta_campaign import MetaCampaign
from app.models.optimization_decision import DecisionRisk, OptimizationActionType, OptimizationDecision
from app.optimization.rules_engine import SignalEvaluation, SignalStatus
from app.prompts.registry import OPTIMIZATION_DECISION_SYSTEM

_ACTION_TYPE_PERMISSIONS = {action_type: "can_manage_campaigns" for action_type in OptimizationActionType}


class DecisionEngineError(Exception):
    pass


def _build_available_action_types(signal_name: str) -> list:
    mapping = {
        "CTR": [OptimizationActionType.CHANGE_HEADLINE, OptimizationActionType.CHANGE_CTA, OptimizationActionType.CREATE_NEW_CREATIVE, OptimizationActionType.CHANGE_AUDIENCE],
        "CPC": [OptimizationActionType.REDUCE_BUDGET, OptimizationActionType.CHANGE_AUDIENCE, OptimizationActionType.PAUSE_AD],
        "CPM": [OptimizationActionType.CHANGE_AUDIENCE, OptimizationActionType.CHANGE_CAMPAIGN_STRUCTURE],
        "CPA": [OptimizationActionType.REDUCE_BUDGET, OptimizationActionType.PAUSE_AD, OptimizationActionType.CHANGE_AUDIENCE],
        "Conversion rate": [OptimizationActionType.CHANGE_HEADLINE, OptimizationActionType.CHANGE_CTA, OptimizationActionType.START_RETARGETING],
        "ROAS": [OptimizationActionType.REDUCE_BUDGET, OptimizationActionType.PAUSE_AD],
        "Spend": [OptimizationActionType.REDUCE_BUDGET, OptimizationActionType.PAUSE_AD],
        "Revenue": [OptimizationActionType.INCREASE_BUDGET, OptimizationActionType.DUPLICATE_WINNING_VARIATION],
        "Campaign objective": [OptimizationActionType.CHANGE_CAMPAIGN_STRUCTURE],
    }
    return mapping.get(signal_name, [OptimizationActionType.PAUSE_AD, OptimizationActionType.REDUCE_BUDGET])


def generate_decision(
    db: Session, *, organization_id: uuid.UUID, meta_campaign: MetaCampaign, signal: SignalEvaluation, actor_user_id: Optional[uuid.UUID] = None
) -> Optional[OptimizationDecision]:
    if signal.status not in (SignalStatus.TRIGGERED, SignalStatus.CONCERNING):
        return None

    available_actions = _build_available_action_types(signal.signal_name)
    action_names = ", ".join(a.value for a in available_actions)
    campaign_context = f"Campaign: {meta_campaign.name}\nObjective: {meta_campaign.objective.value}\nCurrent daily budget: {meta_campaign.daily_budget_cents} cents"
    evidence_json = {"signal": signal.signal_name, "status": signal.status.value, "detail": signal.detail, "value": signal.value, "baseline_value": signal.baseline_value}

    system = OPTIMIZATION_DECISION_SYSTEM.render_system(
        campaign_context=campaign_context, signal_evidence_json=str(evidence_json), available_action_types=action_names
    )

    provider = get_ai_provider_for_task(AITaskType.OPTIMIZATION_DECISION)
    try:
        result = generate_and_track(
            db, provider, [AIMessage(role="user", content=f"Evaluate this {signal.signal_name} signal and recommend an action.")],
            organization_id=organization_id, actor_user_id=actor_user_id, source=AIUsageSource.OPTIMIZATION_DECISION,
            system=system, prompt_name=OPTIMIZATION_DECISION_SYSTEM.name, prompt_version=OPTIMIZATION_DECISION_SYSTEM.version, max_tokens=800,
        )
    except AIProviderError as exc:
        raise DecisionEngineError(f"AI request failed: {exc}") from exc

    try:
        parsed = extract_json_object(result.text)
    except ValueError as exc:
        raise DecisionEngineError(f"AI response was not valid JSON: {exc}") from exc

    try:
        action_type = OptimizationActionType(parsed["action_type"])
    except (KeyError, ValueError) as exc:
        raise DecisionEngineError(f"AI returned an invalid action_type: {parsed.get('action_type')!r}") from exc
    if action_type not in available_actions:
        raise DecisionEngineError(f"AI chose action_type {action_type.value!r}, not offered for this signal")

    try:
        risk = DecisionRisk(parsed["risk"])
    except (KeyError, ValueError) as exc:
        raise DecisionEngineError(f"AI returned an invalid risk: {parsed.get('risk')!r}") from exc

    try:
        confidence = float(parsed["confidence"])
    except (KeyError, ValueError, TypeError) as exc:
        raise DecisionEngineError(f"AI returned an invalid confidence: {parsed.get('confidence')!r}") from exc
    confidence = max(0.0, min(1.0, confidence))

    observation = parsed.get("observation", "").strip()
    proposed_action = parsed.get("proposed_action", "").strip()
    expected_outcome = parsed.get("expected_outcome", "").strip()
    if not observation or not proposed_action or not expected_outcome:
        raise DecisionEngineError("AI response was missing required text fields")

    decision = OptimizationDecision(
        organization_id=organization_id, meta_campaign_id=meta_campaign.id, observation=observation, evidence_json=evidence_json,
        action_type=action_type, proposed_action=proposed_action, action_payload={}, expected_outcome=expected_outcome,
        confidence=confidence, risk=risk, required_permission=_ACTION_TYPE_PERMISSIONS[action_type],
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)
    return decision
