"""week 9: optimization agent - autonomy settings, decisions, action log

Revision ID: a3c57d0973cb
Revises: dd1d201cff53
Create Date: 2026-09-18

Hand-authored against the real compiled model DDL. Tables in FK-
dependency order: campaign_autonomy_settings, campaign_whitelists ->
optimization_decisions -> automated_action_logs (depends on
optimization_decisions, created in this same migration, so last).
Also extends ai_usage_source with optimization_decision.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a3c57d0973cb"
down_revision: Union[str, None] = "dd1d201cff53"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE ai_usage_source ADD VALUE IF NOT EXISTS 'optimization_decision'")

    autonomy_level = postgresql.ENUM("manual", "assisted", "autonomous", name="autonomy_level")
    autonomy_level.create(op.get_bind(), checkfirst=True)
    autonomy_level_col = postgresql.ENUM("manual", "assisted", "autonomous", name="autonomy_level", create_type=False)

    op.create_table(
        "campaign_autonomy_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("meta_campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("autonomy_level", autonomy_level_col, nullable=False),
        sa.Column("max_daily_spend_cents", sa.BigInteger(), nullable=True),
        sa.Column("max_budget_increase_percent", sa.Integer(), nullable=True),
        sa.Column("max_automated_actions_per_day", sa.Integer(), nullable=True),
        sa.Column("auto_executable_action_types", sa.JSON(), nullable=False),
        sa.Column("is_emergency_stopped", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("emergency_stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("emergency_stopped_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("emergency_stop_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["meta_campaign_id"], ["meta_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["emergency_stopped_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("meta_campaign_id", name="uq_campaign_autonomy_settings_meta_campaign_id"),
    )
    op.create_index("ix_campaign_autonomy_settings_meta_campaign_id", "campaign_autonomy_settings", ["meta_campaign_id"])

    op.create_table(
        "campaign_whitelists",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("meta_campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("added_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["meta_campaign_id"], ["meta_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["added_by_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("meta_campaign_id", name="uq_campaign_whitelists_meta_campaign_id"),
    )
    op.create_index("ix_campaign_whitelists_organization_id", "campaign_whitelists", ["organization_id"])
    op.create_index("ix_campaign_whitelists_meta_campaign_id", "campaign_whitelists", ["meta_campaign_id"])

    optimization_action_type = postgresql.ENUM(
        "pause_ad", "reduce_budget", "increase_budget", "change_audience", "create_new_creative",
        "change_headline", "change_cta", "duplicate_winning_variation", "start_retargeting", "change_campaign_structure",
        name="optimization_action_type",
    )
    optimization_action_type.create(op.get_bind(), checkfirst=True)
    optimization_action_type_col = postgresql.ENUM(
        "pause_ad", "reduce_budget", "increase_budget", "change_audience", "create_new_creative",
        "change_headline", "change_cta", "duplicate_winning_variation", "start_retargeting", "change_campaign_structure",
        name="optimization_action_type", create_type=False,
    )

    decision_risk = postgresql.ENUM("low", "medium", "high", name="decision_risk")
    decision_risk.create(op.get_bind(), checkfirst=True)
    decision_risk_col = postgresql.ENUM("low", "medium", "high", name="decision_risk", create_type=False)

    decision_status = postgresql.ENUM(
        "recommended", "approved", "rejected", "auto_approved", "executed", "execution_failed", "expired", name="decision_status"
    )
    decision_status.create(op.get_bind(), checkfirst=True)
    decision_status_col = postgresql.ENUM(
        "recommended", "approved", "rejected", "auto_approved", "executed", "execution_failed", "expired", name="decision_status", create_type=False
    )

    op.create_table(
        "optimization_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("meta_campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("observation", sa.Text(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("action_type", optimization_action_type_col, nullable=False),
        sa.Column("proposed_action", sa.Text(), nullable=False),
        sa.Column("action_payload", sa.JSON(), nullable=False),
        sa.Column("expected_outcome", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("risk", decision_risk_col, nullable=False),
        sa.Column("required_permission", sa.String(length=100), nullable=False),
        sa.Column("status", decision_status_col, nullable=False),
        sa.Column("resulting_approval_request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome_json", sa.JSON(), nullable=True),
        sa.Column("outcome_recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["meta_campaign_id"], ["meta_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resulting_approval_request_id"], ["approval_requests.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_optimization_decisions_organization_id", "optimization_decisions", ["organization_id"])
    op.create_index("ix_optimization_decisions_meta_campaign_id", "optimization_decisions", ["meta_campaign_id"])

    op.create_table(
        "automated_action_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("meta_campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("optimization_decision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("executed_via", sa.String(length=20), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["meta_campaign_id"], ["meta_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["optimization_decision_id"], ["optimization_decisions.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_automated_action_logs_organization_id", "automated_action_logs", ["organization_id"])
    op.create_index("ix_automated_action_logs_meta_campaign_id", "automated_action_logs", ["meta_campaign_id"])
    op.create_index("ix_automated_action_logs_optimization_decision_id", "automated_action_logs", ["optimization_decision_id"])


def downgrade() -> None:
    op.drop_index("ix_automated_action_logs_optimization_decision_id", table_name="automated_action_logs")
    op.drop_index("ix_automated_action_logs_meta_campaign_id", table_name="automated_action_logs")
    op.drop_index("ix_automated_action_logs_organization_id", table_name="automated_action_logs")
    op.drop_table("automated_action_logs")

    op.drop_index("ix_optimization_decisions_meta_campaign_id", table_name="optimization_decisions")
    op.drop_index("ix_optimization_decisions_organization_id", table_name="optimization_decisions")
    op.drop_table("optimization_decisions")
    postgresql.ENUM(name="decision_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="decision_risk").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="optimization_action_type").drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_campaign_whitelists_meta_campaign_id", table_name="campaign_whitelists")
    op.drop_index("ix_campaign_whitelists_organization_id", table_name="campaign_whitelists")
    op.drop_table("campaign_whitelists")

    op.drop_index("ix_campaign_autonomy_settings_meta_campaign_id", table_name="campaign_autonomy_settings")
    op.drop_table("campaign_autonomy_settings")
    postgresql.ENUM(name="autonomy_level").drop(op.get_bind(), checkfirst=True)
