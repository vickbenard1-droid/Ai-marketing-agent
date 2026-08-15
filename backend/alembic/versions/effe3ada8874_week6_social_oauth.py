"""week 6: organic social platforms, connected account columns, oauth_states

Revision ID: effe3ada8874
Revises: 62efee233690
Create Date: 2026-09-25

Hand-authored against the SQLAlchemy models, verified via offline SQL
dry-run (alembic upgrade/downgrade --sql) the same way as every prior
migration. projects and connected_accounts tables already exist (created
in the initial Week 1 migration) - this migration only:
  1. Extends platform_type with the 6 Week 6 organic-posting values
     (ALTER TYPE ... ADD VALUE, same pattern as ai_usage_source/
     brand_voice in prior weeks).
  2. Adds 3 new columns to connected_accounts (token_expires_at,
     granted_scopes, last_error).
  3. Creates oauth_states, the new table backing the OAuth CSRF flow.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "effe3ada8874"
down_revision: Union[str, None] = "62efee233690"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_PLATFORM_VALUES = [
    "facebook_page",
    "instagram_business",
    "linkedin_page",
    "x_account",
    "tiktok_account",
    "youtube_channel",
]


def upgrade() -> None:
    for value in NEW_PLATFORM_VALUES:
        op.execute(f"ALTER TYPE platform_type ADD VALUE IF NOT EXISTS '{value}'")

    op.add_column("connected_accounts", sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("connected_accounts", sa.Column("granted_scopes", sa.String(length=1000), nullable=True))
    op.add_column("connected_accounts", sa.Column("last_error", sa.Text(), nullable=True))

    op.create_table(
        "oauth_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("state_value", sa.String(length=255), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("initiated_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform_type", sa.String(length=50), nullable=False),
        sa.Column("code_verifier", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["initiated_by_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("state_value", name="uq_oauth_states_state_value"),
    )
    op.create_index("ix_oauth_states_state_value", "oauth_states", ["state_value"])


def downgrade() -> None:
    op.drop_index("ix_oauth_states_state_value", table_name="oauth_states")
    op.drop_table("oauth_states")

    op.drop_column("connected_accounts", "last_error")
    op.drop_column("connected_accounts", "granted_scopes")
    op.drop_column("connected_accounts", "token_expires_at")

    # Note: PostgreSQL does not support removing a value from an existing
    # enum type (no ALTER TYPE ... DROP VALUE) - same permanent
    # limitation documented in the Week 4/5 migrations. The 6 organic
    # platform values added to platform_type in upgrade() are not
    # removed here.
