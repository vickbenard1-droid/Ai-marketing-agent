"""
Lead management service.

The one place Lead rows are created and stage-transitioned - every
ingestion source funnels through create_lead(); transition_stage() is
the ONLY function that changes Lead.stage, always writing the matching
LeadStageTransition row in the same operation.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.leads.scoring import compute_and_save_score
from app.models.lead import Lead, LeadSource, LeadStage
from app.models.lead_stage_transition import LeadStageTransition


class LeadServiceError(Exception):
    pass


def create_lead(
    db: Session, *, organization_id: uuid.UUID, source: LeadSource, full_name: Optional[str] = None, email: Optional[str] = None,
    phone: Optional[str] = None, source_external_id: Optional[str] = None, attributed_meta_campaign_id: Optional[uuid.UUID] = None,
    product_interest: Optional[str] = None, disclosed_budget_cents: Optional[int] = None, initial_stage: LeadStage = LeadStage.NEW_LEAD,
) -> Lead:
    if not email and not phone and not full_name:
        raise LeadServiceError("A lead needs at least one of full_name, email, or phone to be usable")

    lead = Lead(
        organization_id=organization_id, source=source, full_name=full_name, email=email, phone=phone,
        source_external_id=source_external_id, attributed_meta_campaign_id=attributed_meta_campaign_id,
        product_interest=product_interest, disclosed_budget_cents=disclosed_budget_cents, stage=initial_stage,
    )
    db.add(lead)
    db.flush()
    db.add(LeadStageTransition(lead_id=lead.id, from_stage=None, to_stage=initial_stage, changed_at=datetime.now(timezone.utc)))
    db.commit()
    db.refresh(lead)
    compute_and_save_score(db, lead)
    db.refresh(lead)
    return lead


def transition_stage(db: Session, *, lead: Lead, to_stage: LeadStage, changed_by_user_id: Optional[uuid.UUID] = None, note: Optional[str] = None) -> Lead:
    from_stage = lead.stage
    lead.stage = to_stage
    db.add(LeadStageTransition(lead_id=lead.id, from_stage=from_stage, to_stage=to_stage, changed_by_user_id=changed_by_user_id, changed_at=datetime.now(timezone.utc), note=note))
    db.commit()
    db.refresh(lead)
    compute_and_save_score(db, lead)
    db.refresh(lead)
    return lead


def get_lead(db: Session, *, organization_id: uuid.UUID, lead_id: uuid.UUID) -> Lead:
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.organization_id == organization_id).first()
    if not lead:
        raise LeadServiceError("Lead not found")
    return lead


def list_leads(db: Session, organization_id: uuid.UUID, *, stage: Optional[LeadStage] = None, source: Optional[LeadSource] = None, assigned_to_user_id: Optional[uuid.UUID] = None) -> list:
    query = db.query(Lead).filter(Lead.organization_id == organization_id)
    if stage is not None:
        query = query.filter(Lead.stage == stage)
    if source is not None:
        query = query.filter(Lead.source == source)
    if assigned_to_user_id is not None:
        query = query.filter(Lead.assigned_to_user_id == assigned_to_user_id)
    return query.order_by(Lead.created_at.desc()).all()


def assign_lead(db: Session, *, lead: Lead, assigned_to_user_id: Optional[uuid.UUID]) -> Lead:
    lead.assigned_to_user_id = assigned_to_user_id
    db.commit()
    db.refresh(lead)
    return lead


def update_lead_notes(db: Session, *, lead: Lead, notes: str) -> Lead:
    lead.notes = notes
    db.commit()
    db.refresh(lead)
    return lead
