import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_org_member, require_permission
from app.db.session import get_db
from app.db.seed_roles import ROLE_DISPLAY_NAMES
from app.models.organization import OrganizationMember, Role
from app.organizations.members_service import (
    MemberError,
    invite_member,
    list_members,
    remove_member,
    update_member_role,
)
from app.schemas.auth import MessageResponse
from app.schemas.member import (
    InviteMemberRequest,
    OrganizationMemberPublic,
    RolePublic,
    UpdateMemberRoleRequest,
)

router = APIRouter(prefix="/organizations/current/members", tags=["members"])
roles_router = APIRouter(prefix="/roles", tags=["roles"])


def _to_public(member: OrganizationMember) -> OrganizationMemberPublic:
    return OrganizationMemberPublic(
        id=member.id,
        user_id=member.user_id,
        email=member.user.email,
        full_name=member.user.full_name,
        role=RolePublic.model_validate(member.role),
    )


@router.get("", response_model=list[OrganizationMemberPublic])
def list_organization_members(
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    """Any member can see the team list — visibility isn't gated behind
    can_manage_members, only mutation is."""
    members = list_members(db, member.organization_id)
    return [_to_public(m) for m in members]


@router.post("", response_model=OrganizationMemberPublic, status_code=status.HTTP_201_CREATED)
def add_organization_member(
    payload: InviteMemberRequest,
    member: OrganizationMember = Depends(require_permission("can_manage_members")),
    db: Session = Depends(get_db),
):
    try:
        new_member = invite_member(
            db,
            organization_id=member.organization_id,
            actor_user_id=member.user_id,
            email=payload.email,
            role_name=payload.role_name,
        )
    except MemberError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return _to_public(new_member)


@router.patch("/{member_id}", response_model=OrganizationMemberPublic)
def update_organization_member_role(
    member_id: uuid.UUID,
    payload: UpdateMemberRoleRequest,
    member: OrganizationMember = Depends(require_permission("can_manage_members")),
    db: Session = Depends(get_db),
):
    try:
        updated = update_member_role(
            db,
            organization_id=member.organization_id,
            actor_user_id=member.user_id,
            member_id=member_id,
            role_name=payload.role_name,
        )
    except MemberError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return _to_public(updated)


@router.delete("/{member_id}", response_model=MessageResponse)
def remove_organization_member(
    member_id: uuid.UUID,
    member: OrganizationMember = Depends(require_permission("can_manage_members")),
    db: Session = Depends(get_db),
):
    try:
        remove_member(
            db, organization_id=member.organization_id, actor_user_id=member.user_id, member_id=member_id
        )
    except MemberError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return MessageResponse(message="Member removed")


@roles_router.get("", response_model=list[RolePublic])
def list_available_roles(
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    """
    All 6 system roles, for populating the role picker when inviting or
    editing a member. Org membership is required (not just auth) so this
    stays consistent with every other tenant-scoped endpoint, even though
    the role list itself isn't tenant-specific data.
    """
    roles = db.query(Role).all()
    # Order matches ROLE_DISPLAY_NAMES (owner -> viewer, most to least
    # privileged) rather than DB insertion order, which is more useful for
    # a UI picker.
    order = list(ROLE_DISPLAY_NAMES.keys())
    roles.sort(key=lambda r: order.index(r.name) if r.name in order else len(order))
    return roles
