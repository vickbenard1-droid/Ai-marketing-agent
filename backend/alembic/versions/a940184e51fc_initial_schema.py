"""initial schema: users, organizations, roles, organization_members,
projects, connected_accounts, audit_logs

Revision ID: a940184e51fc
Revises:
Create Date: 2026-08-14

This migration was authored by hand against the SQLAlchemy models in
app/models rather than via `alembic revision --autogenerate`, because no
live Postgres instance was reachable in the environment that generated it.
It mirrors the models field-for-field. Before running in a real environment,
it's good practice to run `alembic check` (or diff `alembic upgrade head`
against `--autogenerate`) once a DB is available, to confirm there's no
drift.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a940184e51fc"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users ---------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- roles -----------------------------------------------------------
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("can_manage_billing", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("can_manage_members", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("can_manage_projects", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("can_manage_integrations", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("can_execute_ai_actions", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("can_view_only", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_unique_constraint("uq_roles_name", "roles", ["name"])

    # --- organizations -----------------------------------------------------
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("plan_type", sa.String(length=50), nullable=False, server_default="free"),
        sa.Column("is_agency", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    # --- organization_members ----------------------------------------------
    op.create_table(
        "organization_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_user"),
    )
    op.create_index(
        "ix_organization_members_organization_id", "organization_members", ["organization_id"]
    )
    op.create_index("ix_organization_members_user_id", "organization_members", ["user_id"])

    # --- projects ------------------------------------------------------
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("website_url", sa.String(length=500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("industry", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_projects_organization_id", "projects", ["organization_id"])

    # --- connected_accounts -------------------------------------------------
    # Explicit, single CREATE TYPE for each enum (checkfirst=True makes this
    # idempotent against a live DB). The enum instances used inside the
    # column definitions below pass create_type=False so op.create_table
    # doesn't *also* try to emit CREATE TYPE for them — without that,
    # Postgres would see two CREATE TYPE statements for the same name.
    platform_type = postgresql.ENUM(
        "meta_ads",
        "google_ads",
        "tiktok_ads",
        "linkedin",
        "instagram",
        "facebook",
        "youtube",
        "wordpress",
        "shopify",
        "woocommerce",
        "google_analytics",
        "google_search_console",
        name="platform_type",
    )
    connection_status = postgresql.ENUM(
        "pending", "connected", "expired", "error", "disconnected", name="connection_status"
    )
    platform_type.create(op.get_bind(), checkfirst=True)
    connection_status.create(op.get_bind(), checkfirst=True)

    platform_type_col = postgresql.ENUM(
        "meta_ads",
        "google_ads",
        "tiktok_ads",
        "linkedin",
        "instagram",
        "facebook",
        "youtube",
        "wordpress",
        "shopify",
        "woocommerce",
        "google_analytics",
        "google_search_console",
        name="platform_type",
        create_type=False,
    )
    connection_status_col = postgresql.ENUM(
        "pending",
        "connected",
        "expired",
        "error",
        "disconnected",
        name="connection_status",
        create_type=False,
    )

    op.create_table(
        "connected_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", platform_type_col, nullable=False),
        sa.Column("status", connection_status_col, nullable=False, server_default="pending"),
        sa.Column("external_account_id", sa.String(length=255), nullable=True),
        sa.Column("external_account_name", sa.String(length=255), nullable=True),
        sa.Column("encrypted_credentials", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_connected_accounts_organization_id", "connected_accounts", ["organization_id"]
    )
    op.create_index("ix_connected_accounts_project_id", "connected_accounts", ["project_id"])

    # --- audit_logs ------------------------------------------------------
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=True),
        sa.Column("resource_id", sa.String(length=255), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", postgresql.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_audit_logs_organization_id", "audit_logs", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_organization_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_connected_accounts_project_id", table_name="connected_accounts")
    op.drop_index("ix_connected_accounts_organization_id", table_name="connected_accounts")
    op.drop_table("connected_accounts")
    postgresql.ENUM(name="connection_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="platform_type").drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_projects_organization_id", table_name="projects")
    op.drop_table("projects")

    op.drop_index("ix_organization_members_user_id", table_name="organization_members")
    op.drop_index("ix_organization_members_organization_id", table_name="organization_members")
    op.drop_table("organization_members")

    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_table("organizations")

    op.drop_constraint("uq_roles_name", "roles", type_="unique")
    op.drop_table("roles")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
