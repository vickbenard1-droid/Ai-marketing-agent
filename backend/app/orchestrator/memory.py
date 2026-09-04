"""
Agent memory query module.

The spec's memory categories, mapped to what this app actually has -
NOT a new parallel data store, since most categories already have a
real, authoritative source:
- Business knowledge -> app.knowledge.service.get_business_knowledge
  (Week 4, already covers products/audience/brand voice/recent activity)
- Previous decisions / successful & failed strategies ->
  app.models.agent_decision.AgentDecision (this week - genuinely new,
  nothing tracked this before)
- Campaign performance -> app.analytics.service.rollup_totals (Week 8,
  real MetricSnapshot data)
- Customer information -> app.models.lead.Lead (Week 10, real leads)
- Brand voice -> folded into get_business_knowledge already

get_relevant_memory() assembles a single real-data bundle for the
planner/an agent to ground itself in, mirroring the same "gather real
data first, let the AI only narrate/reason over it" discipline used
throughout this app - never a vector-similarity RAG lookup, since every
one of these categories is small enough per organization to just query
directly and completely; a RAG index would add complexity without
adding real information this app doesn't already have a precise way to
fetch.
"""
import uuid
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.analytics.metrics import compute_all
from app.analytics.service import rollup_totals
from app.knowledge.service import get_business_knowledge
from app.models.agent_decision import AgentDecision, DecisionOutcome
from app.models.lead import Lead


@dataclass
class RelevantMemory:
    business_knowledge: str
    recent_performance: dict
    successful_strategies: list
    failed_strategies: list
    recent_customer_summary: dict


def get_successful_strategies(db: Session, organization_id: uuid.UUID, *, limit: int = 5) -> list:
    rows = db.query(AgentDecision).filter(AgentDecision.organization_id == organization_id, AgentDecision.outcome == DecisionOutcome.SUCCESSFUL).order_by(AgentDecision.created_at.desc()).limit(limit).all()
    return [{"agent_name": r.agent_name, "goal": r.goal_description, "summary": r.decision_summary, "outcome_notes": r.outcome_notes} for r in rows]


def get_failed_strategies(db: Session, organization_id: uuid.UUID, *, limit: int = 5) -> list:
    rows = db.query(AgentDecision).filter(AgentDecision.organization_id == organization_id, AgentDecision.outcome == DecisionOutcome.FAILED).order_by(AgentDecision.created_at.desc()).limit(limit).all()
    return [{"agent_name": r.agent_name, "goal": r.goal_description, "summary": r.decision_summary, "outcome_notes": r.outcome_notes} for r in rows]


def get_recent_decisions(db: Session, organization_id: uuid.UUID, *, agent_name: Optional[str] = None, limit: int = 10) -> list:
    query = db.query(AgentDecision).filter(AgentDecision.organization_id == organization_id)
    if agent_name:
        query = query.filter(AgentDecision.agent_name == agent_name)
    return query.order_by(AgentDecision.created_at.desc()).limit(limit).all()


def record_decision_outcome(db: Session, *, decision_id: uuid.UUID, outcome: DecisionOutcome, outcome_notes: Optional[str] = None) -> AgentDecision:
    decision = db.get(AgentDecision, decision_id)
    if not decision:
        raise ValueError("Decision not found")
    decision.outcome = outcome
    decision.outcome_notes = outcome_notes
    db.commit()
    db.refresh(decision)
    return decision


def get_relevant_memory(db: Session, organization_id: uuid.UUID, *, days: int = 30) -> RelevantMemory:
    knowledge = get_business_knowledge(db, organization_id)

    date_stop = date.today()
    date_start = date_stop - timedelta(days=days)
    totals = rollup_totals(db, organization_id, date_start=date_start, date_stop=date_stop)
    derived = compute_all(totals)

    lead_count = db.query(Lead).filter(Lead.organization_id == organization_id, Lead.created_at >= date_start).count()

    return RelevantMemory(
        business_knowledge=knowledge.render(),
        recent_performance={"raw": asdict(totals), "derived": asdict(derived)},
        successful_strategies=get_successful_strategies(db, organization_id),
        failed_strategies=get_failed_strategies(db, organization_id),
        recent_customer_summary={"new_leads_in_period": lead_count},
    )
