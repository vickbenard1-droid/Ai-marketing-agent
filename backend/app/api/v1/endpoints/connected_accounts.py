"""
Connected account endpoints.

Two different auth models coexist here, deliberately:
- start_connect / list / disconnect / reauthorize are normal authenticated
  API calls (Bearer token + X-Organization-Id), gated on
  can_manage_integrations (seeded in Week 2 anticipating this).
- The callback endpoint is NOT authenticated the normal way - it's hit by
  a redirect from the platform's own OAuth server via the person's
  browser, which carries neither a Bearer token nor an X-Organization-Id
  header. Its org/project/user context comes entirely from the
  server-side OAuthState row looked up by the state parameter (see
  app/oauth/service.py::_consume_state) - that lookup, not a normal auth
  dependency, is what proves the request is legitimate. This is the same
  reasoning as why the state token exists at all: it's simultaneously the
  CSRF defense and the only correct way to recover "who started this."
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_org_member, require_permission
from app.core.config import settings
from app.db.session import get_db
from app.models.organization import OrganizationMember
from app.oauth.registry import get_oauth_provider, list_supported_platforms
from app.oauth.service import (
    OAuthFlowError,
    disconnect_account,
    get_connected_account,
    handle_callback,
    list_connected_accounts,
    reauthorize_account,
    start_connect_flow,
)
from app.schemas.auth import MessageResponse
from app.schemas.connected_account import (
    ConnectedAccountPublic,
    StartConnectRequest,
    StartConnectResponse,
    SupportedPlatform,
)

router = APIRouter(tags=["connected-accounts"])


@router.get("/oauth/platforms", response_model=list[SupportedPlatform])
def list_platforms():
    """No auth required — this just tells the frontend which platforms
    exist and whether this deployment has credentials configured for
    each, so it can gray out an unconfigured platform's Connect button
    with an honest reason rather than letting the person click into a
    flow that's guaranteed to fail."""
    result = []
    for platform_type in list_supported_platforms():
        provider = get_oauth_provider(platform_type)
        result.append(
            SupportedPlatform(
                platform=platform_type,
                display_name=provider.display_name,
                configured=provider.is_configured(),
            )
        )
    return result


@router.post("/oauth/{platform_type}/connect", response_model=StartConnectResponse)
def start_connect(
    platform_type: str,
    payload: StartConnectRequest,
    member: OrganizationMember = Depends(require_permission("can_manage_integrations")),
    db: Session = Depends(get_db),
):
    try:
        authorize_url = start_connect_flow(
            db,
            organization_id=member.organization_id,
            project_id=payload.project_id,
            initiated_by_user_id=member.user_id,
            platform_type=platform_type,
        )
    except OAuthFlowError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return StartConnectResponse(authorize_url=authorize_url)


@router.get("/oauth/{platform_type}/callback")
def oauth_callback(
    platform_type: str,
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    See module docstring — deliberately unauthenticated in the normal
    sense; state IS the authentication here. Returns a redirect rather
    than JSON, since this endpoint is hit by a top-level browser
    navigation (the platform's redirect), not a fetch() call — an
    API-shaped JSON response would just render as a raw blob in the
    person's browser instead of taking them back into the app.
    """
    try:
        account = handle_callback(db, platform_type=platform_type, state_value=state, code=code)
        return RedirectResponse(
            url=f"{settings.FRONTEND_BASE_URL}/integrations?connected={account.platform.value}"
        )
    except OAuthFlowError as e:
        return RedirectResponse(url=f"{settings.FRONTEND_BASE_URL}/integrations?error={e}")


@router.get("/connected-accounts", response_model=list[ConnectedAccountPublic])
def list_my_connected_accounts(
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    return list_connected_accounts(db, member.organization_id)


@router.get("/connected-accounts/{account_id}", response_model=ConnectedAccountPublic)
def get_my_connected_account(
    account_id: uuid.UUID,
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    try:
        return get_connected_account(db, organization_id=member.organization_id, account_id=account_id)
    except OAuthFlowError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/connected-accounts/{account_id}/disconnect", response_model=ConnectedAccountPublic)
def disconnect_my_account(
    account_id: uuid.UUID,
    member: OrganizationMember = Depends(require_permission("can_manage_integrations")),
    db: Session = Depends(get_db),
):
    try:
        return disconnect_account(
            db, organization_id=member.organization_id, actor_user_id=member.user_id, account_id=account_id
        )
    except OAuthFlowError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/connected-accounts/{account_id}/reauthorize", response_model=StartConnectResponse)
def reauthorize_my_account(
    account_id: uuid.UUID,
    member: OrganizationMember = Depends(require_permission("can_manage_integrations")),
    db: Session = Depends(get_db),
):
    try:
        account = get_connected_account(db, organization_id=member.organization_id, account_id=account_id)
        authorize_url = reauthorize_account(
            db,
            organization_id=member.organization_id,
            project_id=account.project_id,
            initiated_by_user_id=member.user_id,
            account_id=account_id,
        )
    except OAuthFlowError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return StartConnectResponse(authorize_url=authorize_url)
