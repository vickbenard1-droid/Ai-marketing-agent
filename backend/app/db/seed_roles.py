"""
Seeds the system-default Roles.

Week 2 replaces the original 4-role set (owner, admin, member, viewer) with
the 6 roles the product spec calls for: Owner, Admin, Manager, Analyst,
Content Manager, Viewer. "member" is retired — see migration
de1e8e2c9a3f_week2_roles_and_business_profile.py for how any existing
memberships pointing at "member" are safely reassigned to "manager" before
the row is removed, rather than being silently orphaned.

Run with: python -m app.db.seed_roles
Idempotent — safe to run multiple times (upserts by name).
"""
from app.db.session import SessionLocal
from app.models.organization import Role

SYSTEM_ROLES = [
    {
        "name": "owner",
        "description": "Full control, including billing and org deletion",
        "can_manage_billing": True,
        "can_manage_members": True,
        "can_manage_projects": True,
        "can_manage_integrations": True,
        "can_execute_ai_actions": True,
        "can_manage_campaigns": True,
        "can_manage_content": True,
        "can_view_analytics": True,
        "can_view_only": False,
    },
    {
        "name": "admin",
        "description": "Manage members, projects, and integrations",
        "can_manage_billing": False,
        "can_manage_members": True,
        "can_manage_projects": True,
        "can_manage_integrations": True,
        "can_execute_ai_actions": True,
        "can_manage_campaigns": True,
        "can_manage_content": True,
        "can_view_analytics": True,
        "can_view_only": False,
    },
    {
        "name": "manager",
        "description": "Run day-to-day campaigns and content, no billing or member management",
        "can_manage_billing": False,
        "can_manage_members": False,
        "can_manage_projects": True,
        "can_manage_integrations": False,
        "can_execute_ai_actions": True,
        "can_manage_campaigns": True,
        "can_manage_content": True,
        "can_view_analytics": True,
        "can_view_only": False,
    },
    {
        "name": "analyst",
        "description": "Views performance data and reporting; cannot change campaigns or content",
        "can_manage_billing": False,
        "can_manage_members": False,
        "can_manage_projects": False,
        "can_manage_integrations": False,
        "can_execute_ai_actions": False,
        "can_manage_campaigns": False,
        "can_manage_content": False,
        "can_view_analytics": True,
        "can_view_only": True,
    },
    {
        "name": "content_manager",
        "description": "Creates and manages content; no campaign spend or member control",
        "can_manage_billing": False,
        "can_manage_members": False,
        "can_manage_projects": False,
        "can_manage_integrations": False,
        "can_execute_ai_actions": True,
        "can_manage_campaigns": False,
        "can_manage_content": True,
        "can_view_analytics": True,
        "can_view_only": False,
    },
    {
        "name": "viewer",
        "description": "Read-only access",
        "can_manage_billing": False,
        "can_manage_members": False,
        "can_manage_projects": False,
        "can_manage_integrations": False,
        "can_execute_ai_actions": False,
        "can_manage_campaigns": False,
        "can_manage_content": False,
        "can_view_analytics": True,
        "can_view_only": True,
    },
]

# Display-friendly labels for the frontend (role.name -> human label). Kept
# here, next to the role definitions, so the two never drift apart.
ROLE_DISPLAY_NAMES = {
    "owner": "Owner",
    "admin": "Admin",
    "manager": "Manager",
    "analyst": "Analyst",
    "content_manager": "Content Manager",
    "viewer": "Viewer",
}


def seed_roles() -> None:
    db = SessionLocal()
    try:
        for role_data in SYSTEM_ROLES:
            existing = db.query(Role).filter(Role.name == role_data["name"]).first()
            if existing:
                for key, value in role_data.items():
                    setattr(existing, key, value)
            else:
                db.add(Role(**role_data))
        db.commit()
        print(f"Seeded {len(SYSTEM_ROLES)} system roles.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_roles()
