"""week 7: meta ads integration

Revision ID: 5adf88c68501
Revises: 87063b34bf26
Create Date: 2026-09-01

Hand-authored against the real compiled model DDL, verified via offline
SQL dry-run before writing this file. Tables created in FK-dependency
order.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "5adf88c68501"
down_revision: Union[str, None] = "87063b34bf26"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "meta_ad_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connected_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_ad_account_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("timezone_name", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connected_account_id"], ["connected_accounts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("external_ad_account_id", name="uq_meta_ad_accounts_external_ad_account_id"),
    )
    op.create_index("ix_meta_ad_accounts_organization_id", "meta_ad_accounts", ["organization_id"])
    op.create_index("ix_meta_ad_accounts_connected_account_id", "meta_ad_accounts", ["connected_account_id"])

    op.create_table(
        "ad_account_spend_limits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("meta_ad_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("daily_spend_limit_cents", sa.BigInteger(), nullable=False),
        sa.Column("is_emergency_stopped", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("emergency_stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("emergency_stopped_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("emergency_stop_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["meta_ad_account_id"], ["meta_ad_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["emergency_stopped_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("meta_ad_account_id", name="uq_ad_account_spend_limits_meta_ad_account_id"),
    )
    op.create_index(
        "ix_ad_account_spend_limits_meta_ad_account_id", "ad_account_spend_limits", ["meta_ad_account_id"]
    )

    meta_campaign_objective = postgresql.ENUM(
        "OUTCOME_AWARENESS",
        "OUTCOME_TRAFFIC",
        "OUTCOME_ENGAGEMENT",
        "OUTCOME_LEADS",
        "OUTCOME_SALES",
        "OUTCOME_APP_PROMOTION",
        name="meta_campaign_objective",
    )
    meta_campaign_objective.create(op.get_bind(), checkfirst=True)
    meta_campaign_objective_col = postgresql.ENUM(
        "OUTCOME_AWARENESS",
        "OUTCOME_TRAFFIC",
        "OUTCOME_ENGAGEMENT",
        "OUTCOME_LEADS",
        "OUTCOME_SALES",
        "OUTCOME_APP_PROMOTION",
        name="meta_campaign_objective",
        create_type=False,
    )

    meta_campaign_status = postgresql.ENUM("ACTIVE", "PAUSED", "DELETED", "ARCHIVED", name="meta_campaign_status")
    meta_campaign_status.create(op.get_bind(), checkfirst=True)
    meta_campaign_status_col = postgresql.ENUM(
        "ACTIVE", "PAUSED", "DELETED", "ARCHIVED", name="meta_campaign_status", create_type=False
    )

    op.create_table(
        "meta_campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("meta_ad_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("external_campaign_id", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("objective", meta_campaign_objective_col, nullable=False),
        sa.Column("status", meta_campaign_status_col, nullable=False),
        sa.Column("daily_budget_cents", sa.BigInteger(), nullable=True),
        sa.Column("lifetime_budget_cents", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["meta_ad_account_id"], ["meta_ad_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_campaign_id"], ["campaigns.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("external_campaign_id", name="uq_meta_campaigns_external_campaign_id"),
    )
    op.create_index("ix_meta_campaigns_organization_id", "meta_campaigns", ["organization_id"])
    op.create_index("ix_meta_campaigns_meta_ad_account_id", "meta_campaigns", ["meta_ad_account_id"])

    op.create_table(
        "meta_campaign_spend_limits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("meta_campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("daily_spend_limit_cents", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["meta_campaign_id"], ["meta_campaigns.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("meta_campaign_id", name="uq_meta_campaign_spend_limits_meta_campaign_id"),
    )
    op.create_index(
        "ix_meta_campaign_spend_limits_meta_campaign_id", "meta_campaign_spend_limits", ["meta_campaign_id"]
    )

    meta_ad_set_status = postgresql.ENUM("ACTIVE", "PAUSED", "DELETED", "ARCHIVED", name="meta_ad_set_status")
    meta_ad_set_status.create(op.get_bind(), checkfirst=True)
    meta_ad_set_status_col = postgresql.ENUM(
        "ACTIVE", "PAUSED", "DELETED", "ARCHIVED", name="meta_ad_set_status", create_type=False
    )

    op.create_table(
        "meta_ad_sets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("meta_campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_ad_set_id", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", meta_ad_set_status_col, nullable=False),
        sa.Column("daily_budget_cents", sa.BigInteger(), nullable=True),
        sa.Column("targeting_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["meta_campaign_id"], ["meta_campaigns.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("external_ad_set_id", name="uq_meta_ad_sets_external_ad_set_id"),
    )
    op.create_index("ix_meta_ad_sets_meta_campaign_id", "meta_ad_sets", ["meta_campaign_id"])

    meta_ad_status = postgresql.ENUM(
        "ACTIVE", "PAUSED", "DELETED", "ARCHIVED", "IN_REVIEW", "REJECTED", name="meta_ad_status"
    )
    meta_ad_status.create(op.get_bind(), checkfirst=True)
    meta_ad_status_col = postgresql.ENUM(
        "ACTIVE", "PAUSED", "DELETED", "ARCHIVED", "IN_REVIEW", "REJECTED", name="meta_ad_status", create_type=False
    )

    op.create_table(
        "meta_ads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("meta_ad_set_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_ad_id", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", meta_ad_status_col, nullable=False),
        sa.Column("headline", sa.String(length=255), nullable=True),
        sa.Column("primary_text", sa.Text(), nullable=True),
        sa.Column("call_to_action", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["meta_ad_set_id"], ["meta_ad_sets.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("external_ad_id", name="uq_meta_ads_external_ad_id"),
    )
    op.create_index("ix_meta_ads_meta_ad_set_id", "meta_ads", ["meta_ad_set_id"])

    meta_insight_entity_type = postgresql.ENUM("campaign", "ad_set", "ad", name="meta_insight_entity_type")
    meta_insight_entity_type.create(op.get_bind(), checkfirst=True)
    meta_insight_entity_type_col = postgresql.ENUM(
        "campaign", "ad_set", "ad", name="meta_insight_entity_type", create_type=False
    )

    op.create_table(
        "meta_insight_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("meta_ad_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", meta_insight_entity_type_col, nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("impressions", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("clicks", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("spend_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("reach", sa.BigInteger(), nullable=True),
        sa.Column("leads_count", sa.Integer(), nullable=True),
        sa.Column("purchases_count", sa.Integer(), nullable=True),
        sa.Column("revenue_cents", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=False),
    )
    op.create_index("ix_meta_insight_snapshots_meta_ad_account_id", "meta_insight_snapshots", ["meta_ad_account_id"])
    op.create_index("ix_meta_insight_snapshots_entity_id", "meta_insight_snapshots", ["entity_id"])


def downgrade() -> None:
    op.drop_index("ix_meta_insight_snapshots_entity_id", table_name="meta_insight_snapshots")
    op.drop_index("ix_meta_insight_snapshots_meta_ad_account_id", table_name="meta_insight_snapshots")
    op.drop_table("meta_insight_snapshots")
    postgresql.ENUM(name="meta_insight_entity_type").drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_meta_ads_meta_ad_set_id", table_name="meta_ads")
    op.drop_table("meta_ads")
    postgresql.ENUM(name="meta_ad_status").drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_meta_ad_sets_meta_campaign_id", table_name="meta_ad_sets")
    op.drop_table("meta_ad_sets")
    postgresql.ENUM(name="meta_ad_set_status").drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_meta_campaign_spend_limits_meta_campaign_id", table_name="meta_campaign_spend_limits")
    op.drop_table("meta_campaign_spend_limits")

    op.drop_index("ix_meta_campaigns_meta_ad_account_id", table_name="meta_campaigns")
    op.drop_index("ix_meta_campaigns_organization_id", table_name="meta_campaigns")
    op.drop_table("meta_campaigns")
    postgresql.ENUM(name="meta_campaign_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="meta_campaign_objective").drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_ad_account_spend_limits_meta_ad_account_id", table_name="ad_account_spend_limits")
    op.drop_table("ad_account_spend_limits")

    op.drop_index("ix_meta_ad_accounts_connected_account_id", table_name="meta_ad_accounts")
    op.drop_index("ix_meta_ad_accounts_organization_id", table_name="meta_ad_accounts")
    op.drop_table("meta_ad_accounts")
