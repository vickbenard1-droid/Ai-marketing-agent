"""Lead management endpoints - CRUD, pipeline transitions, qualification, follow-up, sales analytics, sales agent."""
import uuid
from datetime import date as date_type
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

import app.leads.followup as followup_service
import app.leads.ingestion as ingestion
import app.leads.qualification as qualification
import app.leads.sales_agent as sales_agent
import app.leads.sales_analytics as sales_analytics
import app.leads.service as lead_service
from app.auth.dependencies import get_current_org_member, require_permission
from app.db.session import get_db
from app.models.lead import LeadSource, LeadStage
from app.models.lead_follow_up import LeadFollowUp
from app.models.lead_stage_transition import LeadStageTransition
from app.models.organization import OrganizationMember
from app.schemas.leads import (
    AskSalesQuestionRequest, AssignLeadRequest, CreateManualLeadRequest, GenerateFollowUpRequest,
    LeadFollowUpPublic, LeadPublic, LeadStageTransitionPublic, QualificationCriteriaPublic,
    QualificationResultPublic, SalesAgentAnswerPublic, SalesAnalyticsPublic, SetQualificationCriteriaRequest,
    TransitionStageRequest, UpdateLeadNotesRequest,
)

router = APIRouter(prefix="/leads", tags=["leads"])


def _get_lead_or_404(db: Session, organization_id: uuid.UUID, lead_id: uuid.UUID):
    try:
        return lead_service.get_lead(db, organization_id=organization_id, lead_id=lead_id)
    except lead_service.LeadServiceError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")


@router.get("", response_model=list[LeadPublic])
def list_leads(stage: Optional[LeadStage] = Query(default=None), source: Optional[LeadSource] = Query(default=None), assigned_to_user_id: Optional[uuid.UUID] = Query(default=None), member: OrganizationMember = Depends(get_current_org_member), db: Session = Depends(get_db)):
    return lead_service.list_leads(db, member.organization_id, stage=stage, source=source, assigned_to_user_id=assigned_to_user_id)


@router.post("", response_model=LeadPublic, status_code=status.HTTP_201_CREATED)
def create_manual_lead(payload: CreateManualLeadRequest, member: OrganizationMember = Depends(require_permission("can_manage_campaigns")), db: Session = Depends(get_db)):
    try:
        return ingestion.ingest_manual_lead(db, organization_id=member.organization_id, full_name=payload.full_name, email=payload.email, phone=payload.phone, product_interest=payload.product_interest, disclosed_budget_cents=payload.disclosed_budget_cents, attributed_meta_campaign_id=payload.attributed_meta_campaign_id)
    except lead_service.LeadServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{lead_id}", response_model=LeadPublic)
def get_lead(lead_id: uuid.UUID, member: OrganizationMember = Depends(get_current_org_member), db: Session = Depends(get_db)):
    return _get_lead_or_404(db, member.organization_id, lead_id)


@router.get("/{lead_id}/transitions", response_model=list[LeadStageTransitionPublic])
def get_lead_transitions(lead_id: uuid.UUID, member: OrganizationMember = Depends(get_current_org_member), db: Session = Depends(get_db)):
    _get_lead_or_404(db, member.organization_id, lead_id)
    return db.query(LeadStageTransition).filter(LeadStageTransition.lead_id == lead_id).order_by(LeadStageTransition.changed_at).all()


@router.post("/{lead_id}/transition", response_model=LeadPublic)
def transition_lead_stage(lead_id: uuid.UUID, payload: TransitionStageRequest, member: OrganizationMember = Depends(require_permission("can_manage_campaigns")), db: Session = Depends(get_db)):
    lead = _get_lead_or_404(db, member.organization_id, lead_id)
    return lead_service.transition_stage(db, lead=lead, to_stage=payload.to_stage, changed_by_user_id=member.user_id, note=payload.note)


@router.post("/{lead_id}/assign", response_model=LeadPublic)
def assign_lead(lead_id: uuid.UUID, payload: AssignLeadRequest, member: OrganizationMember = Depends(require_permission("can_manage_campaigns")), db: Session = Depends(get_db)):
    lead = _get_lead_or_404(db, member.organization_id, lead_id)
    return lead_service.assign_lead(db, lead=lead, assigned_to_user_id=payload.assigned_to_user_id)


@router.post("/{lead_id}/notes", response_model=LeadPublic)
def update_lead_notes(lead_id: uuid.UUID, payload: UpdateLeadNotesRequest, member: OrganizationMember = Depends(require_permission("can_manage_campaigns")), db: Session = Depends(get_db)):
    lead = _get_lead_or_404(db, member.organization_id, lead_id)
    return lead_service.update_lead_notes(db, lead=lead, notes=payload.notes)


@router.get("/qualification/criteria", response_model=QualificationCriteriaPublic)
def get_qualification_criteria_endpoint(member: OrganizationMember = Depends(get_current_org_member), db: Session = Depends(get_db)):
    return qualification.get_qualification_criteria(db, member.organization_id)


@router.put("/qualification/criteria", response_model=QualificationCriteriaPublic)
def set_qualification_criteria_endpoint(payload: SetQualificationCriteriaRequest, member: OrganizationMember = Depends(require_permission("can_manage_campaigns")), db: Session = Depends(get_db)):
    return qualification.set_qualification_criteria(db, organization_id=member.organization_id, minimum_score=payload.minimum_score, minimum_disclosed_budget_cents=payload.minimum_disclosed_budget_cents, require_product_interest=payload.require_product_interest)


@router.get("/{lead_id}/qualification", response_model=QualificationResultPublic)
def evaluate_lead_qualification(lead_id: uuid.UUID, member: OrganizationMember = Depends(get_current_org_member), db: Session = Depends(get_db)):
    lead = _get_lead_or_404(db, member.organization_id, lead_id)
    criteria = qualification.get_qualification_criteria(db, member.organization_id)
    result = qualification.evaluate_qualification(lead, criteria)
    return QualificationResultPublic(qualifies=result.qualifies, reasons=result.reasons)


@router.post("/{lead_id}/qualify", response_model=LeadPublic)
def qualify_lead_endpoint(lead_id: uuid.UUID, member: OrganizationMember = Depends(require_permission("can_manage_campaigns")), db: Session = Depends(get_db)):
    lead = _get_lead_or_404(db, member.organization_id, lead_id)
    return qualification.qualify_lead(db, lead=lead, changed_by_user_id=member.user_id)


@router.get("/{lead_id}/follow-ups", response_model=list[LeadFollowUpPublic])
def list_follow_ups(lead_id: uuid.UUID, member: OrganizationMember = Depends(get_current_org_member), db: Session = Depends(get_db)):
    _get_lead_or_404(db, member.organization_id, lead_id)
    return db.query(LeadFollowUp).filter(LeadFollowUp.lead_id == lead_id, LeadFollowUp.organization_id == member.organization_id).order_by(LeadFollowUp.created_at.desc()).all()


@router.post("/{lead_id}/follow-ups", response_model=LeadFollowUpPublic, status_code=status.HTTP_201_CREATED)
def generate_follow_up(lead_id: uuid.UUID, payload: GenerateFollowUpRequest, member: OrganizationMember = Depends(require_permission("can_manage_campaigns")), db: Session = Depends(get_db)):
    lead = _get_lead_or_404(db, member.organization_id, lead_id)
    try:
        return followup_service.generate_follow_up(db, organization_id=member.organization_id, lead=lead, channel=payload.channel, tone=payload.tone, actor_user_id=member.user_id)
    except followup_service.FollowUpError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/follow-ups/{follow_up_id}/send", response_model=LeadFollowUpPublic)
def send_follow_up(follow_up_id: uuid.UUID, member: OrganizationMember = Depends(require_permission("can_manage_campaigns")), db: Session = Depends(get_db)):
    follow_up = db.query(LeadFollowUp).filter(LeadFollowUp.id == follow_up_id, LeadFollowUp.organization_id == member.organization_id).first()
    if not follow_up:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Follow-up not found")
    lead = _get_lead_or_404(db, member.organization_id, follow_up.lead_id)
    try:
        return followup_service.send_follow_up(db, follow_up=follow_up, lead=lead)
    except followup_service.FollowUpChannelNotSendableError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/analytics/summary", response_model=SalesAnalyticsPublic)
def get_sales_analytics(date_start: date_type = Query(...), date_stop: date_type = Query(...), member: OrganizationMember = Depends(get_current_org_member), db: Session = Depends(get_db)):
    return sales_analytics.compute_sales_analytics(db, member.organization_id, date_start=date_start, date_stop=date_stop)


@router.post("/analytics/ask", response_model=SalesAgentAnswerPublic)
def ask_sales_agent(payload: AskSalesQuestionRequest, member: OrganizationMember = Depends(require_permission("can_manage_campaigns")), db: Session = Depends(get_db)):
    try:
        answer = sales_agent.ask_sales_question(db, organization_id=member.organization_id, actor_user_id=member.user_id, question=payload.question, date_start=date_type.fromisoformat(payload.date_start), date_stop=date_type.fromisoformat(payload.date_stop))
    except sales_agent.SalesAgentError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return SalesAgentAnswerPublic(answer_text=answer.answer_text, data_used=answer.data_used)
