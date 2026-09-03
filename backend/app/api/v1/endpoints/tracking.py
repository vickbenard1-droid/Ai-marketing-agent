"""
Public website tracking endpoints.

Deliberately UNAUTHENTICATED (no JWT/org header) - these are called
directly from a business's own public website by anonymous visitors'
browsers, which have no way to hold this app's own credentials. The
WebsiteTrackingKey in the request body is what identifies which
organization an event belongs to (see app.analytics.website_tracking's
own docstring on why that key is safe to expose in public page source).

Rate-limited to guard against abuse from a public, unauthenticated
endpoint, using this app's existing slowapi limiter infrastructure.
"""
from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.orm import Session
from fastapi import Depends

from app.analytics.website_tracking import record_conversion, record_page_view, resolve_tracking_key
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.schemas.analytics import TrackConversionRequest, TrackPageViewRequest

router = APIRouter(prefix="/track", tags=["tracking"])

_PUBLIC_TRACKING_LIMIT = "120/minute"


@router.post("/page-view", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(_PUBLIC_TRACKING_LIMIT)
def track_page_view(request: Request, payload: TrackPageViewRequest, db: Session = Depends(get_db)):
    organization_id = resolve_tracking_key(db, payload.tracking_key)
    if not organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown tracking key")
    record_page_view(
        db,
        organization_id=organization_id,
        visitor_id=payload.visitor_id,
        page_url=payload.page_url,
        utm_json=payload.utm_json,
    )


@router.post("/conversion", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(_PUBLIC_TRACKING_LIMIT)
def track_conversion(request: Request, payload: TrackConversionRequest, db: Session = Depends(get_db)):
    organization_id = resolve_tracking_key(db, payload.tracking_key)
    if not organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown tracking key")
    record_conversion(
        db,
        organization_id=organization_id,
        visitor_id=payload.visitor_id,
        conversion_type_name=payload.conversion_type_name,
        conversion_value_cents=payload.conversion_value_cents,
        page_url=payload.page_url,
        utm_json=payload.utm_json,
    )
