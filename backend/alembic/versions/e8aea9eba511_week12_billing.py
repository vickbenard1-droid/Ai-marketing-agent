"""week 12: billing - subscription_plans, organizations.subscription_plan_id

Revision ID: e8aea9eba511
Revises: 49855c74fdf9
Create Date: 2026-11-05

Hand-authored against the real compiled model DDL. subscription_plans
is created first (no FK dependencies of its own), then
subscription_plan_id is added to the EXISTING organizations table via
op.add_column - organizations.plan_type (the Week 1 unenforced string
placeholder) is deliberately left untouched, confirmed genuinely unused
anywhere else in the codebase before this week's real billing work
began, so removing it is out of scope for this migration.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e8aea9eba511"
down_revision: Union[str, None] = "49855c74fdf9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscription_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("monthly_price_cents", sa.Integer(), nullable=False),
        sa.Column("max_ai_tokens_per_month", sa.Integer(), nullable=True),
        sa.Column("max_campaigns", sa.Integer(), nullable=True),
        sa.Column("max_connected_accounts", sa.Integer(), nullable=True),
        sa.Column("max_content_generations_per_month", sa.Integer(), nullable=True),
        sa.Column("max_automated_actions_per_month", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("name", name="uq_subscription_plans_name"),
    )

    op.add_column("organizations", sa.Column("subscription_plan_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_organizations_subscription_plan_id",
        "organizations",
        "subscription_plans",
        ["subscription_plan_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_organizations_subscription_plan_id", "organizations", type_="foreignkey")
    op.drop_column("organizations", "subscription_plan_id")
    op.drop_table("subscription_plans")
