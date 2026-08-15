"""week 6 part 2: scheduled_posts, publishing_logs

Revision ID: 265ad56649a3
Revises: effe3ada8874
Create Date: 2026-09-28

Hand-authored against the SQLAlchemy models, verified via offline SQL
dry-run the same way as every prior migration. Purely additive - 2 new
tables, no changes to existing ones.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "265ad56649a3"
down_revision: Union[str, None] = "effe3ada8874"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    scheduled_post_status = postgresql.ENUM(
        "draft", "scheduled", "publishing", "published", "failed", name="scheduled_post_status"
    )
    scheduled_post_status.create(op.get_bind(), checkfirst=True)
    scheduled_post_status_col = postgresql.ENUM(
        "draft",
        "scheduled",
        "publishing",
        "published",
        "failed",
        name="scheduled_post_status",
        create_type=False,
    )

    op.create_table(
        "scheduled_posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connected_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", scheduled_post_status_col, nullable=False, server_default="draft"),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_post_id", sa.String(length=255), nullable=True),
        sa.Column("external_post_url", sa.String(length=500), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ai_recommended_post_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ai_recommended_platform", sa.String(length=50), nullable=True),
        sa.Column("ai_recommended_format", sa.String(length=100), nullable=True),
        sa.Column("ai_recommended_hashtags", postgresql.ARRAY(sa.String(length=50)), nullable=True),
        sa.Column("ai_recommendation_rationale", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["content_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connected_account_id"], ["connected_accounts.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_scheduled_posts_organization_id", "scheduled_posts", ["organization_id"])
    op.create_index("ix_scheduled_posts_content_id", "scheduled_posts", ["content_id"])
    op.create_index("ix_scheduled_posts_connected_account_id", "scheduled_posts", ["connected_account_id"])

    publishing_log_outcome = postgresql.ENUM("success", "failure", name="publishing_log_outcome")
    publishing_log_outcome.create(op.get_bind(), checkfirst=True)
    publishing_log_outcome_col = postgresql.ENUM(
        "success", "failure", name="publishing_log_outcome", create_type=False
    )

    op.create_table(
        "publishing_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("scheduled_post_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("outcome", publishing_log_outcome_col, nullable=False),
        sa.Column("request_summary", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["scheduled_post_id"], ["scheduled_posts.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_publishing_logs_scheduled_post_id", "publishing_logs", ["scheduled_post_id"])


def downgrade() -> None:
    op.drop_index("ix_publishing_logs_scheduled_post_id", table_name="publishing_logs")
    op.drop_table("publishing_logs")
    postgresql.ENUM(name="publishing_log_outcome").drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_scheduled_posts_connected_account_id", table_name="scheduled_posts")
    op.drop_index("ix_scheduled_posts_content_id", table_name="scheduled_posts")
    op.drop_index("ix_scheduled_posts_organization_id", table_name="scheduled_posts")
    op.drop_table("scheduled_posts")
    postgresql.ENUM(name="scheduled_post_status").drop(op.get_bind(), checkfirst=True)
