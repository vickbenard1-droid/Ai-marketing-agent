"""
Lead qualification module.

Qualification is a distinct concept from scoring - a score is
continuous; qualification is a mechanical business-rule DECISION,
deliberately not AI-driven (same reasoning as Week 9's rules/decision
split - "does this lead meet our criteria" is a fixed, testable rule, not
a judgment call needing AI reasoning).
"""
import uuid
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from app.leads.service import transition_stage
from app.models.lead import Lead, LeadStage
from app.models.lead_qualification_settings import LeadQualificationSettings


@dataclass
class QualificationCriteria:
    minimum_score: int
    minimum_disclosed_budget_cents: Optional[int]
    require_product_interest: bool


@dataclass
class QualificationResult:
    qualifies: bool
    reasons: list = field(default_factory=list)


def get_qualification_criteria(db: Session, organization_id: uuid.UUID) -> QualificationCriteria:
    settings = db.query(LeadQualificationSettings).filter(LeadQualificationSettings.organization_id == organization_id).first()
    if not settings:
        return QualificationCriteria(minimum_score=40, minimum_disclosed_budget_cents=None, require_product_interest=False)
    return QualificationCriteria(minimum_score=settings.minimum_score, minimum_disclosed_budget_cents=settings.minimum_disclosed_budget_cents, require_product_interest=settings.require_product_interest)


def set_qualification_criteria(db: Session, *, organization_id: uuid.UUID, minimum_score: int, minimum_disclosed_budget_cents: Optional[int], require_product_interest: bool) -> QualificationCriteria:
    settings = db.query(LeadQualificationSettings).filter(LeadQualificationSettings.organization_id == organization_id).first()
    if not settings:
        settings = LeadQualificationSettings(organization_id=organization_id)
        db.add(settings)
    settings.minimum_score = minimum_score
    settings.minimum_disclosed_budget_cents = minimum_disclosed_budget_cents
    settings.require_product_interest = require_product_interest
    db.commit()
    db.refresh(settings)
    return QualificationCriteria(minimum_score=settings.minimum_score, minimum_disclosed_budget_cents=settings.minimum_disclosed_budget_cents, require_product_interest=settings.require_product_interest)


def evaluate_qualification(lead: Lead, criteria: QualificationCriteria) -> QualificationResult:
    reasons = []
    qualifies = True

    if lead.score is None or lead.score < criteria.minimum_score:
        qualifies = False
        reasons.append(f"Score {lead.score} is below the minimum of {criteria.minimum_score}")
    else:
        reasons.append(f"Score {lead.score} meets the minimum of {criteria.minimum_score}")

    if criteria.minimum_disclosed_budget_cents is not None:
        if lead.disclosed_budget_cents is None or lead.disclosed_budget_cents < criteria.minimum_disclosed_budget_cents:
            qualifies = False
            reasons.append(f"Disclosed budget does not meet the minimum of ${criteria.minimum_disclosed_budget_cents / 100:.2f}")

    if criteria.require_product_interest and not lead.product_interest:
        qualifies = False
        reasons.append("No product interest disclosed, which is required")

    return QualificationResult(qualifies=qualifies, reasons=reasons)


def qualify_lead(db: Session, *, lead: Lead, changed_by_user_id: Optional[uuid.UUID] = None) -> Lead:
    return transition_stage(db, lead=lead, to_stage=LeadStage.QUALIFIED, changed_by_user_id=changed_by_user_id, note="Marked qualified")
