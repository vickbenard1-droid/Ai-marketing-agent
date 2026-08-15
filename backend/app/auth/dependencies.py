"""
FastAPI dependencies for authentication and authorization.

- get_current_user: decodes the bearer JWT, loads the User.
- get_current_org_member: resolves the caller's membership + role for the
  organization referenced in the request path (X-Organization-Id header
  this week; can move to a path param later without changing callers).
- require_permission: factory that returns a dependency enforcing one
  boolean permission flag on the caller's Role.
"""
import uuid
from typing import Callable

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.organization import OrganizationMember, Role
from app.models.user import User

# tokenUrl is documentation-only (points Swagger UI at the login endpoint).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_error

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise credentials_error

    user_id = payload.get("sub")
    if not user_id:
        raise credentials_error

    user = db.get(User, uuid.UUID(user_id))
    if not user or not user.is_active:
        raise credentials_error

    return user


def get_current_org_member(
    x_organization_id: uuid.UUID = Header(..., description="Active organization context"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrganizationMember:
    """
    Resolves tenant context for the request. Every tenant-scoped endpoint
    should depend on this (directly or via require_permission) rather than
    trusting an organization_id passed in the request body — that's what
    enforces tenant isolation at the API boundary.
    """
    member = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == x_organization_id,
            OrganizationMember.user_id == current_user.id,
        )
        .first()
    )
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this organization",
        )
    return member


def require_permission(permission: str) -> Callable:
    """
    Usage: Depends(require_permission("can_manage_members"))
    Enforces a boolean flag on the caller's Role within the active org.
    """

    def dependency(
        member: OrganizationMember = Depends(get_current_org_member),
        db: Session = Depends(get_db),
    ) -> OrganizationMember:
        role = db.get(Role, member.role_id)
        if not role or not getattr(role, permission, False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {permission}",
            )
        return member

    return dependency
