"""
Content generation endpoints - the AI-cost-incurring half of content
management (see content.py for CRUD/read). All three actions here
(single-content generation, repurposing, SEO) are gated on
can_execute_ai_actions rather than can_manage_content, matching the same
split used for campaigns (campaign_generation.py vs campaigns.py) and
agents (agents.py): managing/editing content doesn't require the
AI-execution permission, but generating new content does, since that's
what actually spends AI provider budget.

Note: RepurposeError is mapped to 400 (validation failure — e.g. no
source provided), separate from ContentGenerationError/SEOGenerationError
mapped to 502 (the AI call itself or its response failed) — a bad request
and an upstream failure are different problems for the client to act on.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.content.generation_service import ContentGenerationError, generate_content
from app.content.repurpose_service import RepurposeError, repurpose_content
from app.content.seo_service import SEOGenerationError, generate_seo
from app.db.session import get_db
from app.models.organization import OrganizationMember
from app.schemas.content import (
    ContentPublic,
    GenerateContentRequest,
    RepurposeBatchPublic,
    RepurposeRequest,
)
from app.schemas.seo import GenerateSEORequest, SEOContentPublic

router = APIRouter(tags=["content-generation"])


@router.post("/content/generate", response_model=ContentPublic)
def generate_content_endpoint(
    payload: GenerateContentRequest,
    member: OrganizationMember = Depends(require_permission("can_execute_ai_actions")),
    db: Session = Depends(get_db),
):
    try:
        return generate_content(
            db,
            organization_id=member.organization_id,
            actor_user_id=member.user_id,
            content_type=payload.content_type,
            source_text=payload.source_text,
            source_url=payload.source_url,
            source_asset_id=payload.source_asset_id,
        )
    except ContentGenerationError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/content/repurpose", response_model=RepurposeBatchPublic)
def repurpose_content_endpoint(
    payload: RepurposeRequest,
    member: OrganizationMember = Depends(require_permission("can_execute_ai_actions")),
    db: Session = Depends(get_db),
):
    try:
        return repurpose_content(
            db,
            organization_id=member.organization_id,
            actor_user_id=member.user_id,
            source_text=payload.source_text,
            source_url=payload.source_url,
            source_asset_id=payload.source_asset_id,
        )
    except RepurposeError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/seo/generate", response_model=SEOContentPublic)
def generate_seo_endpoint(
    payload: GenerateSEORequest,
    member: OrganizationMember = Depends(require_permission("can_execute_ai_actions")),
    db: Session = Depends(get_db),
):
    try:
        return generate_seo(
            db,
            organization_id=member.organization_id,
            actor_user_id=member.user_id,
            topic=payload.topic,
            content_id=payload.content_id,
        )
    except SEOGenerationError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
