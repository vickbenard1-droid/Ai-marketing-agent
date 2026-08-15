"""week 3: AI usage logs, approval requests, conversations, chat messages

Revision ID: 0af813ec3a41
Revises: 92763f7fa341
Create Date: 2026-08-28

Hand-authored against the SQLAlchemy models, same rationale and same
verification method as the Week 1/2 migrations (see those files for the
full explanation): no live Postgres instance is reachable in the
environment that generated this, so the DDL below was cross-checked by
compiling CreateTable() against the postgresql dialect for all 4 new
tables before writing this by hand, and verified end-to-end via
`alembic upgrade/downgrade --sql` (offline mode).

This migration is purely additive — 4 new tables, no changes to existing
ones — so unlike the Week 2 migration there is no data-migration step to
reason about.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0af813ec3a41"
down_revision: Union[str, None] = "92763f7fa341"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- ai_usage_logs -----------------------------------------------------
    ai_usage_source = postgresql.ENUM(
        "marketing_strategy_agent",
        "audience_research_agent",
        "ad_copy_agent",
        "seo_agent",
        "chat",
        name="ai_usage_source",
    )
    ai_usage_source.create(op.get_bind(), checkfirst=True)
    ai_usage_source_col = postgresql.ENUM(
        "marketing_strategy_agent",
        "audience_research_agent",
        "ad_copy_agent",
        "seo_agent",
        "chat",
        name="ai_usage_source",
        create_type=False,
    )

    op.create_table(
        "ai_usage_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source", ai_usage_source_col, nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("prompt_name", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=20), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_ai_usage_logs_organization_id", "ai_usage_logs", ["organization_id"])

    # --- approval_requests -------------------------------------------------
    approval_action_type = postgresql.ENUM(
        "campaign_budget_change",
        "campaign_pause",
        "campaign_launch",
        "content_publish",
        "ad_copy_deploy",
        name="approval_action_type",
    )
    approval_action_type.create(op.get_bind(), checkfirst=True)
    approval_action_type_col = postgresql.ENUM(
        "campaign_budget_change",
        "campaign_pause",
        "campaign_launch",
        "content_publish",
        "ad_copy_deploy",
        name="approval_action_type",
        create_type=False,
    )

    approval_status = postgresql.ENUM(
        "pending", "approved", "rejected", "executed", "expired", name="approval_status"
    )
    approval_status.create(op.get_bind(), checkfirst=True)
    approval_status_col = postgresql.ENUM(
        "pending", "approved", "rejected", "executed", "expired", name="approval_status", create_type=False
    )

    op.create_table(
        "approval_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action_type", approval_action_type_col, nullable=False),
        sa.Column("status", approval_status_col, nullable=False, server_default="pending"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("action_payload", sa.JSON(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_approval_requests_organization_id", "approval_requests", ["organization_id"])

    # --- conversations / chat_messages -------------------------------------
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_conversations_organization_id", "conversations", ["organization_id"])
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])

    chat_role = postgresql.ENUM("user", "assistant", name="chat_role")
    chat_role.create(op.get_bind(), checkfirst=True)
    chat_role_col = postgresql.ENUM("user", "assistant", name="chat_role", create_type=False)

    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", chat_role_col, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_chat_messages_conversation_id", "chat_messages", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_messages_conversation_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    postgresql.ENUM(name="chat_role").drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_conversations_user_id", table_name="conversations")
    op.drop_index("ix_conversations_organization_id", table_name="conversations")
    op.drop_table("conversations")

    op.drop_index("ix_approval_requests_organization_id", table_name="approval_requests")
    op.drop_table("approval_requests")
    postgresql.ENUM(name="approval_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="approval_action_type").drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_ai_usage_logs_organization_id", table_name="ai_usage_logs")
    op.drop_table("ai_usage_logs")
    postgresql.ENUM(name="ai_usage_source").drop(op.get_bind(), checkfirst=True)
