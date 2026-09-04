"""week 11: orchestrator - orchestration_runs, agent_activity_logs, agent_decisions

Revision ID: 49855c74fdf9
Revises: f57027466f19
Create Date: 2026-10-02

Hand-authored against the real compiled model DDL. FK order:
orchestration_runs -> agent_activity_logs (depends on
orchestration_runs and approval_requests) -> agent_decisions
(independent, only depends on organizations). Also extends
ai_usage_source with orchestrator_planning.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "49855c74fdf9"
down_revision: Union[str, None] = "f57027466f19"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE ai_usage_source ADD VALUE IF NOT EXISTS 'orchestrator_planning'")

    orchestration_run_status = postgresql.ENUM("planning", "running", "paused_for_approval", "completed", "failed", "cancelled", name="orchestration_run_status")
    orchestration_run_status.create(op.get_bind(), checkfirst=True)
    orchestration_run_status_col = postgresql.ENUM("planning", "running", "paused_for_approval", "completed", "failed", "cancelled", name="orchestration_run_status", create_type=False)

    op.create_table(
        "orchestration_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("goal_text", sa.Text(), nullable=False),
        sa.Column("plan_json", sa.JSON(), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False),
        sa.Column("status", orchestration_run_status_col, nullable=False),
        sa.Column("final_summary", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_orchestration_runs_organization_id", "orchestration_runs", ["organization_id"])

    activity_status = postgresql.ENUM("planned", "in_progress", "awaiting_approval", "approved", "rejected", "completed", "failed", name="activity_status")
    activity_status.create(op.get_bind(), checkfirst=True)
    activity_status_col = postgresql.ENUM("planned", "in_progress", "awaiting_approval", "approved", "rejected", "completed", "failed", name="activity_status", create_type=False)

    op.create_table(
        "agent_activity_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("orchestration_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("agent_name", sa.Text(), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=True),
        sa.Column("action_description", sa.Text(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("data_used_json", sa.JSON(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("execution_result_json", sa.JSON(), nullable=True),
        sa.Column("status", activity_status_col, nullable=False),
        sa.Column("requires_approval", sa.Boolean(), nullable=False),
        sa.Column("approval_request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["orchestration_run_id"], ["orchestration_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approval_request_id"], ["approval_requests.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_agent_activity_logs_organization_id", "agent_activity_logs", ["organization_id"])
    op.create_index("ix_agent_activity_logs_orchestration_run_id", "agent_activity_logs", ["orchestration_run_id"])

    decision_outcome = postgresql.ENUM("pending", "successful", "failed", "inconclusive", name="decision_outcome")
    decision_outcome.create(op.get_bind(), checkfirst=True)
    decision_outcome_col = postgresql.ENUM("pending", "successful", "failed", "inconclusive", name="decision_outcome", create_type=False)

    op.create_table(
        "agent_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_name", sa.Text(), nullable=False),
        sa.Column("goal_description", sa.Text(), nullable=True),
        sa.Column("decision_summary", sa.Text(), nullable=False),
        sa.Column("context_json", sa.JSON(), nullable=False),
        sa.Column("outcome", decision_outcome_col, nullable=False),
        sa.Column("outcome_notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_agent_decisions_organization_id", "agent_decisions", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_decisions_organization_id", table_name="agent_decisions")
    op.drop_table("agent_decisions")
    postgresql.ENUM(name="decision_outcome").drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_agent_activity_logs_orchestration_run_id", table_name="agent_activity_logs")
    op.drop_index("ix_agent_activity_logs_organization_id", table_name="agent_activity_logs")
    op.drop_table("agent_activity_logs")
    postgresql.ENUM(name="activity_status").drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_orchestration_runs_organization_id", table_name="orchestration_runs")
    op.drop_table("orchestration_runs")
    postgresql.ENUM(name="orchestration_run_status").drop(op.get_bind(), checkfirst=True)
