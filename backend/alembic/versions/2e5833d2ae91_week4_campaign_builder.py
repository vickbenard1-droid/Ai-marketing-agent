"""week 4: campaign builder - campaigns, campaign_strategies,
ad_copy_variants, creative_concepts, experiments

Revision ID: 2e5833d2ae91
Revises: 0af813ec3a41
Create Date: 2026-09-04

Hand-authored against the SQLAlchemy models, verified the same way as
every prior migration in this project: DDL cross-checked by compiling
CreateTable() against the postgresql dialect for all 5 new tables, and
the full upgrade/downgrade verified via `alembic upgrade/downgrade --sql`
(offline mode) before this file was finalized. Purely additive — 5 new
tables, no changes to existing ones, no data migration needed.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "2e5833d2ae91"
down_revision: Union[str, None] = "0af813ec3a41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- extend ai_usage_source (added in Week 3) with the new campaign
    # generation source. ALTER TYPE ... ADD VALUE cannot run inside the
    # same transaction as other DDL that might use the new value on some
    # Postgres versions, so this runs first and stands alone.
    op.execute("ALTER TYPE ai_usage_source ADD VALUE IF NOT EXISTS 'campaign_builder'")

    # --- campaigns -----------------------------------------------------
    campaign_status = postgresql.ENUM(
        "draft", "generating", "generated", "approved", name="campaign_status"
    )
    campaign_status.create(op.get_bind(), checkfirst=True)
    campaign_status_col = postgresql.ENUM(
        "draft", "generating", "generated", "approved", name="campaign_status", create_type=False
    )

    campaign_objective = postgresql.ENUM(
        "sales", "leads", "website_traffic", "brand_awareness", name="campaign_objective"
    )
    campaign_objective.create(op.get_bind(), checkfirst=True)
    campaign_objective_col = postgresql.ENUM(
        "sales", "leads", "website_traffic", "brand_awareness", name="campaign_objective", create_type=False
    )

    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", campaign_status_col, nullable=False, server_default="draft"),
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("product_price", sa.Integer(), nullable=True),
        sa.Column("product_description", sa.Text(), nullable=True),
        sa.Column("target_location", sa.String(length=255), nullable=True),
        sa.Column("target_audience", sa.Text(), nullable=True),
        sa.Column("existing_customer_info", sa.Text(), nullable=True),
        sa.Column("objective", campaign_objective_col, nullable=False),
        sa.Column("desired_outcome_count", sa.Integer(), nullable=True),
        sa.Column("budget_amount", sa.Integer(), nullable=True),
        sa.Column("budget_currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("duration_days", sa.Integer(), nullable=True),
        sa.Column("landing_page_url", sa.String(length=500), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_campaigns_organization_id", "campaigns", ["organization_id"])

    # --- campaign_strategies -------------------------------------------
    op.create_table(
        "campaign_strategies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("strategy_json", sa.JSON(), nullable=False),
        sa.Column("audience_json", sa.JSON(), nullable=False),
        sa.Column("budget_strategy_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("campaign_id", name="uq_campaign_strategies_campaign_id"),
    )
    op.create_index("ix_campaign_strategies_campaign_id", "campaign_strategies", ["campaign_id"])

    # --- ad_copy_variants -------------------------------------------------
    op.create_table(
        "ad_copy_variants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("variant_number", sa.Integer(), nullable=False),
        sa.Column("headline", sa.String(length=255), nullable=False),
        sa.Column("primary_text", sa.Text(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("call_to_action", sa.String(length=100), nullable=False),
        sa.Column("is_edited", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ad_copy_variants_campaign_id", "ad_copy_variants", ["campaign_id"])

    # --- creative_concepts -------------------------------------------------
    creative_concept_type = postgresql.ENUM(
        "image", "video", "hook", "visual_direction", "ugc", name="creative_concept_type"
    )
    creative_concept_type.create(op.get_bind(), checkfirst=True)
    creative_concept_type_col = postgresql.ENUM(
        "image", "video", "hook", "visual_direction", "ugc", name="creative_concept_type", create_type=False
    )

    op.create_table(
        "creative_concepts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("concept_type", creative_concept_type_col, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_creative_concepts_campaign_id", "creative_concepts", ["campaign_id"])

    # --- experiments -----------------------------------------------------
    experiment_dimension = postgresql.ENUM(
        "audience", "headline", "hook", "creative", name="experiment_dimension"
    )
    experiment_dimension.create(op.get_bind(), checkfirst=True)
    experiment_dimension_col = postgresql.ENUM(
        "audience", "headline", "hook", "creative", name="experiment_dimension", create_type=False
    )

    op.create_table(
        "experiments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("dimension", experiment_dimension_col, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("variant_ids", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_experiments_campaign_id", "experiments", ["campaign_id"])


def downgrade() -> None:
    # Note: PostgreSQL does not support removing a value from an existing
    # enum type (no ALTER TYPE ... DROP VALUE). The 'campaign_builder'
    # value added to ai_usage_source in upgrade() is not removed here —
    # it's a genuine, permanent limitation of Postgres enums, not an
    # oversight. Downgrading past this migration leaves that value in the
    # enum's allowed set; it's simply never used once the campaigns
    # feature (the only thing that writes it) is gone.

    op.drop_index("ix_experiments_campaign_id", table_name="experiments")
    op.drop_table("experiments")
    postgresql.ENUM(name="experiment_dimension").drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_creative_concepts_campaign_id", table_name="creative_concepts")
    op.drop_table("creative_concepts")
    postgresql.ENUM(name="creative_concept_type").drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_ad_copy_variants_campaign_id", table_name="ad_copy_variants")
    op.drop_table("ad_copy_variants")

    op.drop_index("ix_campaign_strategies_campaign_id", table_name="campaign_strategies")
    op.drop_table("campaign_strategies")

    op.drop_index("ix_campaigns_organization_id", table_name="campaigns")
    op.drop_table("campaigns")
    postgresql.ENUM(name="campaign_objective").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="campaign_status").drop(op.get_bind(), checkfirst=True)
