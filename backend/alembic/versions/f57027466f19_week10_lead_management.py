"""week 10: lead-to-sale intelligence - leads, transitions, qualification, follow-ups

Revision ID: f57027466f19
Revises: a3c57d0973cb
Create Date: 2026-09-25

Hand-authored against the real compiled model DDL. FK order: leads ->
lead_stage_transitions (depends on leads) -> lead_qualification_settings
(independent) -> lead_follow_ups (depends on leads). Also extends
ai_usage_source with sales_agent.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f57027466f19"
down_revision: Union[str, None] = "a3c57d0973cb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE ai_usage_source ADD VALUE IF NOT EXISTS 'sales_agent'")

    lead_source = postgresql.ENUM("meta_leads", "website_form", "landing_page", "shopify", "woocommerce", "crm", "manual", name="lead_source")
    lead_source.create(op.get_bind(), checkfirst=True)
    lead_source_col = postgresql.ENUM("meta_leads", "website_form", "landing_page", "shopify", "woocommerce", "crm", "manual", name="lead_source", create_type=False)

    lead_stage = postgresql.ENUM("new_lead", "contacted", "qualified", "interested", "negotiation", "won", "lost", name="lead_stage")
    lead_stage.create(op.get_bind(), checkfirst=True)
    lead_stage_col = postgresql.ENUM("new_lead", "contacted", "qualified", "interested", "negotiation", "won", "lost", name="lead_stage", create_type=False)

    op.create_table(
        "leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("source", lead_source_col, nullable=False),
        sa.Column("source_external_id", sa.String(length=255), nullable=True),
        sa.Column("attributed_meta_campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("stage", lead_stage_col, nullable=False),
        sa.Column("product_interest", sa.String(length=500), nullable=True),
        sa.Column("disclosed_budget_cents", sa.Integer(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("score_factors_json", sa.JSON(), nullable=True),
        sa.Column("score_computed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_to_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["attributed_meta_campaign_id"], ["meta_campaigns.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_leads_organization_id", "leads", ["organization_id"])
    op.create_index("ix_leads_email", "leads", ["email"])

    op.create_table(
        "lead_stage_transitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_stage", lead_stage_col, nullable=True),
        sa.Column("to_stage", lead_stage_col, nullable=False),
        sa.Column("changed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_lead_stage_transitions_lead_id", "lead_stage_transitions", ["lead_id"])

    op.create_table(
        "lead_qualification_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("minimum_score", sa.Integer(), nullable=False),
        sa.Column("minimum_disclosed_budget_cents", sa.Integer(), nullable=True),
        sa.Column("require_product_interest", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("organization_id", name="uq_lead_qualification_settings_organization_id"),
    )
    op.create_index("ix_lead_qualification_settings_organization_id", "lead_qualification_settings", ["organization_id"])

    followup_channel = postgresql.ENUM("email", "whatsapp", "sms", "crm", name="followup_channel")
    followup_channel.create(op.get_bind(), checkfirst=True)
    followup_channel_col = postgresql.ENUM("email", "whatsapp", "sms", "crm", name="followup_channel", create_type=False)

    followup_status = postgresql.ENUM("drafted", "sent", "failed", "not_sendable", name="followup_status")
    followup_status.create(op.get_bind(), checkfirst=True)
    followup_status_col = postgresql.ENUM("drafted", "sent", "failed", "not_sendable", name="followup_status", create_type=False)

    op.create_table(
        "lead_follow_ups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", followup_channel_col, nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", followup_status_col, nullable=False),
        sa.Column("send_error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_lead_follow_ups_organization_id", "lead_follow_ups", ["organization_id"])
    op.create_index("ix_lead_follow_ups_lead_id", "lead_follow_ups", ["lead_id"])


def downgrade() -> None:
    op.drop_index("ix_lead_follow_ups_lead_id", table_name="lead_follow_ups")
    op.drop_index("ix_lead_follow_ups_organization_id", table_name="lead_follow_ups")
    op.drop_table("lead_follow_ups")
    postgresql.ENUM(name="followup_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="followup_channel").drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_lead_qualification_settings_organization_id", table_name="lead_qualification_settings")
    op.drop_table("lead_qualification_settings")

    op.drop_index("ix_lead_stage_transitions_lead_id", table_name="lead_stage_transitions")
    op.drop_table("lead_stage_transitions")

    op.drop_index("ix_leads_email", table_name="leads")
    op.drop_index("ix_leads_organization_id", table_name="leads")
    op.drop_table("leads")
    postgresql.ENUM(name="lead_stage").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="lead_source").drop(op.get_bind(), checkfirst=True)
