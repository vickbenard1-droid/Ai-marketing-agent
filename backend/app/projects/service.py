"""
Project service.

Minimal CRUD - built as a Week 6 prerequisite. ConnectedAccount has
required project_id since Week 1 (see that model's own docstring, which
anticipated this), but no Project API existed until now; every feature
since Week 3 (agents, campaigns, content) deliberately went
organization-scoped instead to avoid this exact gap. Week 6 needs a real
Project to attach social connections to, so this is that minimal API -
not an attempt to fully build out multi-project workflows (campaigns/
content remain organization-scoped; only ConnectedAccount uses Project).

An organization with no projects yet cannot connect a social account
until it creates one - see get_or_create_default_project() for the
one-project-per-org convenience path most single-business organizations
will use without ever thinking about "projects" as a concept.
"""
import uuid

from sqlalchemy.orm import Session

from app.models.project import Project


class ProjectError(Exception):
    """Raised for project failures the API layer should turn into 4xx responses."""


def list_projects(db: Session, organization_id: uuid.UUID) -> list[Project]:
    return (
        db.query(Project)
        .filter(Project.organization_id == organization_id)
        .order_by(Project.created_at.asc())
        .all()
    )


def get_project(db: Session, *, organization_id: uuid.UUID, project_id: uuid.UUID) -> Project:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.organization_id == organization_id)
        .first()
    )
    if not project:
        raise ProjectError("Project not found")
    return project


def create_project(
    db: Session,
    *,
    organization_id: uuid.UUID,
    name: str,
    website_url: str | None = None,
    description: str | None = None,
    industry: str | None = None,
) -> Project:
    project = Project(
        organization_id=organization_id,
        name=name,
        website_url=website_url,
        description=description,
        industry=industry,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def update_project(
    db: Session, *, organization_id: uuid.UUID, project_id: uuid.UUID, updates: dict
) -> Project:
    project = get_project(db, organization_id=organization_id, project_id=project_id)
    for field, value in updates.items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, *, organization_id: uuid.UUID, project_id: uuid.UUID) -> None:
    project = get_project(db, organization_id=organization_id, project_id=project_id)
    db.delete(project)
    db.commit()


def get_or_create_default_project(db: Session, organization_id: uuid.UUID) -> Project:
    """
    Convenience path for the common case (a single-business org that
    never explicitly thinks about "projects"): if the org has exactly one
    project already, or none yet, this returns/creates a single default
    one - the connect-account flow can call this so a person connecting
    their first Facebook Page isn't forced through a "create a project
    first" step that means nothing to them. An org that already has
    multiple projects (the agency case) must pick one explicitly instead
    - this function raises rather than guessing which of several
    projects a new connection belongs to.
    """
    projects = list_projects(db, organization_id)
    if len(projects) == 1:
        return projects[0]
    if len(projects) == 0:
        return create_project(db, organization_id=organization_id, name="Default")
    raise ProjectError(
        "This organization has multiple projects — specify which project this connection belongs to"
    )
