"""
Project endpoints.

Reading requires only org membership. Creating/editing/deleting is gated
on can_manage_projects - seeded in Week 2 anticipating this exact
feature (Owner/Admin/Manager have it, Content Manager/Analyst/Viewer
don't).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_org_member, require_permission
from app.db.session import get_db
from app.models.organization import OrganizationMember
from app.projects.service import (
    ProjectError,
    create_project,
    delete_project,
    get_project,
    list_projects,
    update_project,
)
from app.schemas.auth import MessageResponse
from app.schemas.project import ProjectCreate, ProjectPublic, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectPublic])
def list_my_projects(
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    return list_projects(db, member.organization_id)


@router.post("", response_model=ProjectPublic, status_code=status.HTTP_201_CREATED)
def create_my_project(
    payload: ProjectCreate,
    member: OrganizationMember = Depends(require_permission("can_manage_projects")),
    db: Session = Depends(get_db),
):
    return create_project(db, organization_id=member.organization_id, **payload.model_dump())


@router.get("/{project_id}", response_model=ProjectPublic)
def get_my_project(
    project_id: uuid.UUID,
    member: OrganizationMember = Depends(get_current_org_member),
    db: Session = Depends(get_db),
):
    try:
        return get_project(db, organization_id=member.organization_id, project_id=project_id)
    except ProjectError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{project_id}", response_model=ProjectPublic)
def update_my_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    member: OrganizationMember = Depends(require_permission("can_manage_projects")),
    db: Session = Depends(get_db),
):
    try:
        return update_project(
            db,
            organization_id=member.organization_id,
            project_id=project_id,
            updates=payload.model_dump(exclude_unset=True),
        )
    except ProjectError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{project_id}", response_model=MessageResponse)
def delete_my_project(
    project_id: uuid.UUID,
    member: OrganizationMember = Depends(require_permission("can_manage_projects")),
    db: Session = Depends(get_db),
):
    try:
        delete_project(db, organization_id=member.organization_id, project_id=project_id)
    except ProjectError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return MessageResponse(message="Project deleted")
