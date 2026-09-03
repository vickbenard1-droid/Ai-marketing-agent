"""Analytics endpoints - dashboard rollups, conversion type management, tracking key management."""
import uuid
from dataclasses import asdict
from datetime import date as date_type
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.analytics.metrics import compute_all
from app.analytics.service import (
    AnalyticsError,
    create_conversion_type,
    list_conversion_types,
    rollup_totals,
    seed_default_conversion_types,
)
from app.analytics.website_tracking import get_or_create_tracking_key, regenerate_tracking_key
from app.auth.dependencies import get_current_org_member, require_permission
from app.db.session import get_db
from app.models.connected_account import PlatformType
from app.models.metric_snapshot import MetricEntityType
from app.models.organization import OrganizationMember
from app.schemas.analytics import (
    ConversionTypePublic,
    CreateConversionTypeRequest,
    DashboardResponse,
    TrackingKeyPublic,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    date_start: date_type = Query(...),
    date_stop: date_type = Query(...),
    source: Optional[PlatformType] = Query(default=None),
    entity_type: Optional[MetricEntityType] = Query(default=None),
    entity_id: Optional[uuid.UUID] = Query(default=None),
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    totals = rollup_totals(
        db,
        member.organization_id,
        source=source,
        entity_type=entity_type,
        entity_id=entity_id,
        date_start=date_start,
        date_stop=date_stop,
    )
    derived = compute_all(totals)
    return DashboardResponse(raw=asdict(totals), derived=asdict(derived))


@router.get("/conversion-types", response_model=list[ConversionTypePublic])
def get_conversion_types(
    active_only: bool = Query(default=True),
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    types = list_conversion_types(db, member.organization_id, active_only=active_only)
    if not types:
        types = seed_default_conversion_types(db, member.organization_id)
    return types


@router.post("/conversion-types", response_model=ConversionTypePublic, status_code=status.HTTP_201_CREATED)
def post_conversion_type(
    payload: CreateConversionTypeRequest,
    member: OrganizationMember = Depends(require_permission("can_manage_campaigns")),
    db: Session = Depends(get_db),
):
    try:
        return create_conversion_type(
            db,
            organization_id=member.organization_id,
            name=payload.name,
            category=payload.category,
            description=payload.description,
            counts_as_revenue=payload.counts_as_revenue,
        )
    except AnalyticsError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/tracking-key", response_model=TrackingKeyPublic)
def get_tracking_key(
    member: OrganizationMember = Depends(require_permission("can_manage_integrations")),
    db: Session = Depends(get_db),
):
    return get_or_create_tracking_key(db, member.organization_id)


@router.post("/tracking-key/regenerate", response_model=TrackingKeyPublic)
def post_regenerate_tracking_key(
    member: OrganizationMember = Depends(require_permission("can_manage_integrations")),
    db: Session = Depends(get_db),
):
    return regenerate_tracking_key(db, member.organization_id)
