"""
Organization endpoints.

GET /organizations lists orgs the current user belongs to (their org
switcher data in the frontend). Creating additional orgs is supported now
because a user (e.g. agency owner) may need more than the one auto-created
at registration.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.audit.service import write_audit_log
from app.auth.dependencies import get_current_org_member, get_current_user, require_permission
from app.core.utils import slugify
from app.db.session import get_db
from app.models.organization import Organization, OrganizationMember, Role
from app.models.user import User
from app.schemas.organization import OrganizationCreate, OrganizationPublic, OrganizationUpdate

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("", response_model=list[OrganizationPublic])
def list_my_organizations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    memberships = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.user_id == current_user.id)
        .all()
    )
    return [m.organization for m in memberships]


@router.post("", response_model=OrganizationPublic, status_code=201)
def create_organization(
    payload: OrganizationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    base_slug = slugify(payload.name)
    slug = base_slug
    suffix = 1
    while db.query(Organization).filter(Organization.slug == slug).first():
        suffix += 1
        slug = f"{base_slug}-{suffix}"

    org = Organization(name=payload.name, slug=slug, is_agency=payload.is_agency)
    db.add(org)
    db.flush()

    owner_role = db.query(Role).filter(Role.name == "owner").first()
    db.add(OrganizationMember(organization_id=org.id, user_id=current_user.id, role_id=owner_role.id))

    write_audit_log(
        db,
        organization_id=org.id,
        actor_user_id=current_user.id,
        action="organization.created",
        resource_type="Organization",
        resource_id=str(org.id),
    )

    db.commit()
    db.refresh(org)
    return org


@router.get("/current", response_model=OrganizationPublic)
def get_current_organization(
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    """
    Returns the organization identified by the X-Organization-Id header —
    i.e. the org the frontend's org switcher currently has active. Named
    "current" rather than taking a path param since the active org is
    already established by the header on every tenant-scoped request.
    """
    org = db.get(Organization, member.organization_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


@router.patch("/current", response_model=OrganizationPublic)
def update_current_organization(
    payload: OrganizationUpdate,
    member: OrganizationMember = Depends(require_permission("can_manage_projects")),
    db: Session = Depends(get_db),
):
    """
    Updates the active organization's name (onboarding step 1 — business
    name — lands here, not in the onboarding router, since
    Organization.name is the single source of truth for it; see
    app/models/business_profile.py's module docstring).

    Gated on can_manage_projects rather than can_manage_members: renaming
    the business is closer to "managing the business's setup" than to
    membership administration, and every role above Viewer/Analyst already
    has it.
    """
    org = db.get(Organization, member.organization_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(org, field, value)

    write_audit_log(
        db,
        organization_id=org.id,
        actor_user_id=member.user_id,
        action="organization.updated",
        resource_type="Organization",
        resource_id=str(org.id),
        metadata={"fields": list(updates.keys())},
    )

    db.commit()
    db.refresh(org)
    return org
