"""week 2: user profile fields, expanded role permissions + 6-role reseed,
email_tokens, business_profiles

Revision ID: 92763f7fa341
Revises: a940184e51fc
Create Date: 2026-08-21

Hand-authored against the SQLAlchemy models (see
app/models/user.py, organization.py, email_token.py, business_profile.py)
for the same reason as the initial migration: no live Postgres instance was
reachable in the environment that generated it. DDL for new/changed columns
was cross-checked by compiling CreateTable() against the postgresql dialect
before writing this by hand.

Role transition note: Week 1 seeded 4 roles (owner, admin, member, viewer).
Week 2 replaces "member" with "manager" (plus adds "analyst" and
"content_manager"). Any existing OrganizationMember row pointing at
"member" is reassigned to "manager" *before* the "member" role row is
deleted — never delete-then-orphan. This is a no-op in a fresh database
(no members exist yet), but makes the migration safe to run against a
database that already has real users, which is the point of a migration
vs. just changing the seed script.

Verification note: this migration's DDL (upgrade and downgrade) was
verified via `alembic upgrade/downgrade --sql` (offline mode) against the
postgresql dialect. The data-migration step (the member->manager
reassignment above) cannot run in offline mode — it requires a real
connection to read existing data — and this project's migrations target
Postgres only, so `alembic upgrade` itself can't be exercised end-to-end
against SQLite either (SQLite can't ALTER most constraint types, which the
Week 1 migration already relies on). The reassignment logic itself was
verified by executing the exact same statements directly against a real
SQLAlchemy session seeded with a realistic pre-Week-2 state (an org, a
user, and a membership pointing at a "member" role) and confirming: the
membership ends up pointing at "manager", the "member" role row is gone,
and no row is left dangling. The no-existing-"member"-role branch (a fresh
database) was verified separately as a clean no-op. Run this migration
against a real staging Postgres database before production use, as with
any migration.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "92763f7fa341"
down_revision: Union[str, None] = "a940184e51fc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users: profile fields (Week 2) ---------------------------------
    op.add_column("users", sa.Column("avatar_url", sa.String(length=1000), nullable=True))
    op.add_column("users", sa.Column("phone", sa.String(length=50), nullable=True))
    op.add_column("users", sa.Column("timezone", sa.String(length=100), nullable=True))

    # --- roles: new permission flags (Week 2) ---------------------------
    op.add_column(
        "roles",
        sa.Column("can_manage_campaigns", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "roles",
        sa.Column("can_manage_content", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "roles",
        sa.Column("can_view_analytics", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    # --- role transition: retire "member", add manager/analyst/content_manager ---
    roles = sa.table(
        "roles",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
    )
    org_members = sa.table(
        "organization_members",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("role_id", postgresql.UUID(as_uuid=True)),
    )

    connection = op.get_bind()

    # New roles are inserted with permissive-but-safe defaults here; the
    # authoritative values live in app/db/seed_roles.py and
    # `python -m app.db.seed_roles` should be run after this migration
    # (see README setup instructions) to bring every role's flags in sync
    # with the current SYSTEM_ROLES definition — this migration only needs
    # rows to exist so the foreign key from organization_members resolves.
    import uuid

    manager_id = uuid.uuid4()
    analyst_id = uuid.uuid4()
    content_manager_id = uuid.uuid4()

    op.bulk_insert(
        sa.table(
            "roles",
            sa.column("id", postgresql.UUID(as_uuid=True)),
            sa.column("name", sa.String),
            sa.column("description", sa.String),
            sa.column("can_manage_billing", sa.Boolean),
            sa.column("can_manage_members", sa.Boolean),
            sa.column("can_manage_projects", sa.Boolean),
            sa.column("can_manage_integrations", sa.Boolean),
            sa.column("can_execute_ai_actions", sa.Boolean),
            sa.column("can_view_only", sa.Boolean),
            sa.column("can_manage_campaigns", sa.Boolean),
            sa.column("can_manage_content", sa.Boolean),
            sa.column("can_view_analytics", sa.Boolean),
        ),
        [
            {
                "id": manager_id,
                "name": "manager",
                "description": "Run day-to-day campaigns and content, no billing or member management",
                "can_manage_billing": False,
                "can_manage_members": False,
                "can_manage_projects": True,
                "can_manage_integrations": False,
                "can_execute_ai_actions": True,
                "can_view_only": False,
                "can_manage_campaigns": True,
                "can_manage_content": True,
                "can_view_analytics": True,
            },
            {
                "id": analyst_id,
                "name": "analyst",
                "description": "Views performance data and reporting; cannot change campaigns or content",
                "can_manage_billing": False,
                "can_manage_members": False,
                "can_manage_projects": False,
                "can_manage_integrations": False,
                "can_execute_ai_actions": False,
                "can_view_only": True,
                "can_manage_campaigns": False,
                "can_manage_content": False,
                "can_view_analytics": True,
            },
            {
                "id": content_manager_id,
                "name": "content_manager",
                "description": "Creates and manages content; no campaign spend or member control",
                "can_manage_billing": False,
                "can_manage_members": False,
                "can_manage_projects": False,
                "can_manage_integrations": False,
                "can_execute_ai_actions": True,
                "can_view_only": False,
                "can_manage_campaigns": False,
                "can_manage_content": True,
                "can_view_analytics": True,
            },
        ],
    )

    # Reassign any existing "member" memberships to "manager" before
    # dropping the "member" role row. This step requires a live connection
    # to read current data (op.get_bind().execute() returns None for SELECT
    # in `alembic upgrade --sql` offline mode, since there's no database to
    # read from) — skip it in offline mode rather than crash; offline mode
    # is for generating a DDL script to review, not for running the actual
    # data migration.
    if not op.get_context().as_sql:
        member_row = connection.execute(
            sa.select(roles.c.id).where(roles.c.name == "member")
        ).first()
        if member_row is not None:
            member_role_id = member_row[0]
            connection.execute(
                org_members.update()
                .where(org_members.c.role_id == member_role_id)
                .values(role_id=manager_id)
            )
            connection.execute(roles.delete().where(roles.c.id == member_role_id))

    # --- email_tokens ----------------------------------------------------
    email_token_type = postgresql.ENUM(
        "email_verification", "password_reset", name="email_token_type"
    )
    email_token_type.create(op.get_bind(), checkfirst=True)
    email_token_type_col = postgresql.ENUM(
        "email_verification", "password_reset", name="email_token_type", create_type=False
    )

    op.create_table(
        "email_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_type", email_token_type_col, nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_email_tokens_user_id", "email_tokens", ["user_id"])
    op.create_index("ix_email_tokens_token_hash", "email_tokens", ["token_hash"], unique=True)

    # --- business_profiles -------------------------------------------------
    marketing_goal = postgresql.ENUM(
        "sales", "leads", "website_traffic", "brand_awareness", name="marketing_goal"
    )
    marketing_goal.create(op.get_bind(), checkfirst=True)
    marketing_goal_col = postgresql.ENUM(
        "sales", "leads", "website_traffic", "brand_awareness", name="marketing_goal", create_type=False
    )

    op.create_table(
        "business_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("website_url", sa.String(length=500), nullable=True),
        sa.Column("industry", sa.String(length=150), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("products_services", sa.Text(), nullable=True),
        sa.Column("target_customers", sa.Text(), nullable=True),
        sa.Column("marketing_goal", marketing_goal_col, nullable=True),
        sa.Column("monthly_ad_budget", sa.Integer(), nullable=True),
        sa.Column("budget_currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("social_platforms", postgresql.ARRAY(sa.String(length=50)), nullable=True),
        sa.Column("advertising_platforms", postgresql.ARRAY(sa.String(length=50)), nullable=True),
        sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("onboarding_current_step", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("organization_id", name="uq_business_profiles_organization_id"),
    )
    op.create_index(
        "ix_business_profiles_organization_id", "business_profiles", ["organization_id"]
    )

    # --- revoked_tokens (logout support) ---------------------------------
    op.create_table(
        "revoked_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("jti", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_revoked_tokens_jti", "revoked_tokens", ["jti"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_revoked_tokens_jti", table_name="revoked_tokens")
    op.drop_table("revoked_tokens")

    op.drop_index("ix_business_profiles_organization_id", table_name="business_profiles")
    op.drop_table("business_profiles")
    postgresql.ENUM(name="marketing_goal").drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_email_tokens_token_hash", table_name="email_tokens")
    op.drop_index("ix_email_tokens_user_id", table_name="email_tokens")
    op.drop_table("email_tokens")
    postgresql.ENUM(name="email_token_type").drop(op.get_bind(), checkfirst=True)

    # Role transition is not reversed symmetrically: memberships that were
    # moved from "member" to "manager" stay on "manager" (recreating
    # "member" and guessing which memberships to move back would be
    # destructive guesswork, not a real downgrade). The new role rows are
    # removed; any memberships pointing at them would violate the FK and
    # must be reassigned manually before downgrading a database with real
    # data — this mirrors the upgrade's own safety note.
    op.execute("DELETE FROM roles WHERE name IN ('manager', 'analyst', 'content_manager')")

    op.drop_column("roles", "can_view_analytics")
    op.drop_column("roles", "can_manage_content")
    op.drop_column("roles", "can_manage_campaigns")

    op.drop_column("users", "timezone")
    op.drop_column("users", "phone")
    op.drop_column("users", "avatar_url")
