"""
Lead scoring module.

The "Do not use prohibited or sensitive characteristics" constraint,
treated as a structural property, not a prompt rule.

FACTORS USED: product interest, disclosed budget (only when the lead
themselves disclosed it), engagement (stage transition count), recency,
previous interaction, website engagement.

FACTORS DELIBERATELY EXCLUDED: LOCATION (per the confirmed design
decision, excluded entirely even though a legitimate-use argument could
be made - deliberately conservative rather than relying on a person to
judge case by case). Every protected characteristic under fair-lending/
anti-discrimination law - structurally impossible, since no such field
exists anywhere on Lead. A lead's NAME is present but never read by
this module. No budget/income is ever ESTIMATED - only genuine
self-disclosure is used.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.lead import Lead, LeadStage
from app.models.lead_stage_transition import LeadStageTransition
from app.models.website_tracking_event import WebsiteTrackingEvent

MAX_SCORE = 100
MIN_SCORE = 0


@dataclass
class ScoreFactor:
    name: str
    points: int
    reason: str


@dataclass
class ScoreResult:
    score: int
    factors: list = field(default_factory=list)


def _score_product_interest(lead: Lead) -> Optional[ScoreFactor]:
    if not lead.product_interest or not lead.product_interest.strip():
        return None
    return ScoreFactor("Product interest", 15, f"Expressed interest in: {lead.product_interest[:80]}")


def _score_disclosed_budget(lead: Lead) -> Optional[ScoreFactor]:
    if lead.disclosed_budget_cents is None:
        return None
    return ScoreFactor("Disclosed budget", 15, f"Disclosed a budget of ${lead.disclosed_budget_cents / 100:.2f}")


def _score_engagement(db: Session, lead: Lead) -> Optional[ScoreFactor]:
    transition_count = db.query(func.count(LeadStageTransition.id)).filter(LeadStageTransition.lead_id == lead.id).scalar()
    if not transition_count or transition_count <= 1:
        return None
    points = min(20, (transition_count - 1) * 5)
    return ScoreFactor("Engagement", points, f"Has moved through {transition_count - 1} stage change(s)")


def _score_behaviour_recency(lead: Lead) -> Optional[ScoreFactor]:
    if lead.updated_at is None:
        return None
    updated_at = lead.updated_at if lead.updated_at.tzinfo else lead.updated_at.replace(tzinfo=timezone.utc)
    days_since_update = (datetime.now(timezone.utc) - updated_at).days
    if days_since_update <= 2:
        return ScoreFactor("Recent activity", 15, "Updated within the last 2 days")
    if days_since_update <= 7:
        return ScoreFactor("Recent activity", 8, "Updated within the last week")
    if days_since_update > 30:
        return ScoreFactor("Recent activity", -10, "No activity in over 30 days")
    return None


def _score_previous_interaction(lead: Lead) -> Optional[ScoreFactor]:
    if lead.stage == LeadStage.NEW_LEAD:
        return None
    return ScoreFactor("Previous interaction", 10, f"Already progressed to '{lead.stage.value}'")


def _score_website_engagement(db: Session, lead: Lead, visitor_id: Optional[str]) -> Optional[ScoreFactor]:
    if not visitor_id:
        return None
    event_count = db.query(func.count(WebsiteTrackingEvent.id)).filter(WebsiteTrackingEvent.organization_id == lead.organization_id, WebsiteTrackingEvent.visitor_id == visitor_id).scalar()
    if not event_count or event_count <= 1:
        return None
    points = min(15, (event_count - 1) * 2)
    return ScoreFactor("Website engagement", points, f"{event_count} tracked website events")


def score_lead(db: Session, lead: Lead) -> ScoreResult:
    visitor_id = lead.source_external_id if lead.source.value in ("website_form", "landing_page") else None
    candidate_factors = [
        _score_product_interest(lead),
        _score_disclosed_budget(lead),
        _score_engagement(db, lead),
        _score_behaviour_recency(lead),
        _score_previous_interaction(lead),
        _score_website_engagement(db, lead, visitor_id),
    ]
    factors = [f for f in candidate_factors if f is not None]
    raw_score = sum(f.points for f in factors)
    clamped_score = max(MIN_SCORE, min(MAX_SCORE, raw_score))
    return ScoreResult(score=clamped_score, factors=factors)


def compute_and_save_score(db: Session, lead: Lead) -> Lead:
    result = score_lead(db, lead)
    lead.score = result.score
    lead.score_factors_json = {
        "factors": [{"name": f.name, "points": f.points, "reason": f.reason} for f in result.factors],
        "excluded_factors_note": "This score never uses location, name, or any protected/sensitive characteristic.",
    }
    lead.score_computed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(lead)
    return lead
