"""
Team member management business logic.

Invite (Week 2 scope, see schemas/member.py::InviteMemberRequest docstring)
adds an *existing* user to the org directly — no invite-token/email-accept
flow yet. Role changes and removal both guard against an organization
being left with zero owners, since that would make the org
unmanageable (no one left who can grant billing/member permissions).
"""
from sqlalchemy.orm import Session

from app.audit.service import write_audit_log
from app.models.organization import OrganizationMember, Role
from app.models.user import User


class MemberError(Exception):
    """Raised for member-management failures the API layer turns into 4xx responses."""


def list_members(db: Session, organization_id) -> list[OrganizationMember]:
    return (
        db.query(OrganizationMember)
        .filter(OrganizationMember.organization_id == organization_id)
        .all()
    )


def _owner_count(db: Session, organization_id) -> int:
    owner_role = db.query(Role).filter(Role.name == "owner").first()
    if not owner_role:
        return 0
    return (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.role_id == owner_role.id,
        )
        .count()
    )


def invite_member(
    db: Session, *, organization_id, actor_user_id, email: str, role_name: str
) -> OrganizationMember:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise MemberError(
            "No account exists for that email. They need to create an account first."
        )

    existing = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user.id,
        )
        .first()
    )
    if existing:
        raise MemberError("This person is already a member of the organization")

    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        raise MemberError(f"Unknown role: {role_name}")

    member = OrganizationMember(organization_id=organization_id, user_id=user.id, role_id=role.id)
    db.add(member)
    db.flush()

    write_audit_log(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="member.invited",
        resource_type="OrganizationMember",
        resource_id=str(member.id),
        metadata={"email": email, "role": role_name},
    )

    db.commit()
    db.refresh(member)
    return member


def update_member_role(
    db: Session, *, organization_id, actor_user_id, member_id, role_name: str
) -> OrganizationMember:
    member = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.id == member_id,
            OrganizationMember.organization_id == organization_id,
        )
        .first()
    )
    if not member:
        raise MemberError("Member not found")

    new_role = db.query(Role).filter(Role.name == role_name).first()
    if not new_role:
        raise MemberError(f"Unknown role: {role_name}")

    current_role = db.get(Role, member.role_id)
    if (
        current_role
        and current_role.name == "owner"
        and role_name != "owner"
        and _owner_count(db, organization_id) <= 1
    ):
        raise MemberError(
            "Cannot change this member's role — they are the organization's only owner"
        )

    old_role_name = current_role.name if current_role else None
    member.role_id = new_role.id

    write_audit_log(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="member.role_changed",
        resource_type="OrganizationMember",
        resource_id=str(member.id),
        metadata={"from_role": old_role_name, "to_role": role_name},
    )

    db.commit()
    db.refresh(member)
    return member


def remove_member(db: Session, *, organization_id, actor_user_id, member_id) -> None:
    member = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.id == member_id,
            OrganizationMember.organization_id == organization_id,
        )
        .first()
    )
    if not member:
        raise MemberError("Member not found")

    role = db.get(Role, member.role_id)
    if role and role.name == "owner" and _owner_count(db, organization_id) <= 1:
        raise MemberError("Cannot remove the organization's only owner")

    write_audit_log(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="member.removed",
        resource_type="OrganizationMember",
        resource_id=str(member.id),
        metadata={"removed_user_id": str(member.user_id)},
    )

    db.delete(member)
    db.commit()
