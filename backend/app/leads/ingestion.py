"""
Lead ingestion module.

One function per spec-named source, funneling through create_lead().
Duplicate handling: every function checks for an existing Lead with the
same organization_id + source + source_external_id before creating a
new one (where the source provides a stable external id).
"""
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.leads.service import LeadServiceError, create_lead
from app.models.lead import Lead, LeadSource


def _find_existing_lead(db: Session, *, organization_id: uuid.UUID, source: LeadSource, source_external_id: str) -> Optional[Lead]:
    return db.query(Lead).filter(Lead.organization_id == organization_id, Lead.source == source, Lead.source_external_id == source_external_id).first()


def ingest_meta_lead(db: Session, *, organization_id: uuid.UUID, leadgen_id: str, full_name: Optional[str] = None, email: Optional[str] = None, phone: Optional[str] = None, meta_campaign_id: Optional[uuid.UUID] = None, field_data: Optional[dict] = None) -> Optional[Lead]:
    existing = _find_existing_lead(db, organization_id=organization_id, source=LeadSource.META_LEADS, source_external_id=leadgen_id)
    if existing:
        return None
    product_interest = None
    disclosed_budget_cents = None
    if field_data:
        for key, value in field_data.items():
            key_lower = key.lower()
            if "interest" in key_lower or "product" in key_lower:
                product_interest = str(value)[:500]
            if "budget" in key_lower:
                try:
                    disclosed_budget_cents = int(float(value) * 100)
                except (ValueError, TypeError):
                    pass
    try:
        return create_lead(db, organization_id=organization_id, source=LeadSource.META_LEADS, source_external_id=leadgen_id, full_name=full_name, email=email, phone=phone, attributed_meta_campaign_id=meta_campaign_id, product_interest=product_interest, disclosed_budget_cents=disclosed_budget_cents)
    except LeadServiceError:
        return None


def ingest_website_form_lead(db: Session, *, organization_id: uuid.UUID, visitor_id: str, full_name: Optional[str] = None, email: Optional[str] = None, phone: Optional[str] = None, product_interest: Optional[str] = None, disclosed_budget_cents: Optional[int] = None, is_landing_page: bool = False) -> Optional[Lead]:
    source = LeadSource.LANDING_PAGE if is_landing_page else LeadSource.WEBSITE_FORM
    existing = _find_existing_lead(db, organization_id=organization_id, source=source, source_external_id=visitor_id)
    if existing:
        return None
    try:
        return create_lead(db, organization_id=organization_id, source=source, source_external_id=visitor_id, full_name=full_name, email=email, phone=phone, product_interest=product_interest, disclosed_budget_cents=disclosed_budget_cents)
    except LeadServiceError:
        return None


def _ingest_ecommerce_customer(db: Session, *, organization_id: uuid.UUID, source: LeadSource, external_customer_id: str, full_name: Optional[str], email: Optional[str], phone: Optional[str]) -> Optional[Lead]:
    existing = _find_existing_lead(db, organization_id=organization_id, source=source, source_external_id=external_customer_id)
    if existing:
        return None
    try:
        return create_lead(db, organization_id=organization_id, source=source, source_external_id=external_customer_id, full_name=full_name, email=email, phone=phone)
    except LeadServiceError:
        return None


def ingest_shopify_lead(db: Session, *, organization_id: uuid.UUID, external_customer_id: str, full_name: Optional[str] = None, email: Optional[str] = None, phone: Optional[str] = None) -> Optional[Lead]:
    return _ingest_ecommerce_customer(db, organization_id=organization_id, source=LeadSource.SHOPIFY, external_customer_id=external_customer_id, full_name=full_name, email=email, phone=phone)


def ingest_woocommerce_lead(db: Session, *, organization_id: uuid.UUID, external_customer_id: str, full_name: Optional[str] = None, email: Optional[str] = None, phone: Optional[str] = None) -> Optional[Lead]:
    return _ingest_ecommerce_customer(db, organization_id=organization_id, source=LeadSource.WOOCOMMERCE, external_customer_id=external_customer_id, full_name=full_name, email=email, phone=phone)


def ingest_crm_lead(db: Session, *, organization_id: uuid.UUID, external_contact_id: str, full_name: Optional[str] = None, email: Optional[str] = None, phone: Optional[str] = None) -> Optional[Lead]:
    existing = _find_existing_lead(db, organization_id=organization_id, source=LeadSource.CRM, source_external_id=external_contact_id)
    if existing:
        return None
    try:
        return create_lead(db, organization_id=organization_id, source=LeadSource.CRM, source_external_id=external_contact_id, full_name=full_name, email=email, phone=phone)
    except LeadServiceError:
        return None


def ingest_manual_lead(db: Session, *, organization_id: uuid.UUID, full_name: Optional[str] = None, email: Optional[str] = None, phone: Optional[str] = None, product_interest: Optional[str] = None, disclosed_budget_cents: Optional[int] = None, attributed_meta_campaign_id: Optional[uuid.UUID] = None) -> Lead:
    return create_lead(db, organization_id=organization_id, source=LeadSource.MANUAL, full_name=full_name, email=email, phone=phone, product_interest=product_interest, disclosed_budget_cents=disclosed_budget_cents, attributed_meta_campaign_id=attributed_meta_campaign_id)
