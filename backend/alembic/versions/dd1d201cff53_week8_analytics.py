"""week 8: unified analytics layer

Revision ID: dd1d201cff53
Revises: 5adf88c68501
Create Date: 2026-09-10

Hand-authored against the real compiled model DDL, verified via offline
SQL dry-run before writing this file. Tables in FK-dependency order:
metric_snapshots, conversion_types -> conversion_events (depends on
conversion_types), website_tracking_keys, website_tracking_events.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "dd1d201cff53"
down_revision: Union[str, None] = "5adf88c68501"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    metric_entity_type = postgresql.ENUM("organization", "campaign", "ad", "page", name="metric_entity_type")
    metric_entity_type.create(op.get_bind(), checkfirst=True)
    metric_entity_type_col = postgresql.ENUM(
        "organization", "campaign", "ad", "page", name="metric_entity_type", create_type=False
    )

    op.create_table(
        "metric_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", postgresql.ENUM(name="platform_type", create_type=False), nullable=False),
        sa.Column("entity_type", metric_entity_type_col, nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("impressions", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("clicks", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("spend_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("leads_count", sa.Integer(), nullable=True),
        sa.Column("purchases_count", sa.Integer(), nullable=True),
        sa.Column("revenue_cents", sa.BigInteger(), nullable=True),
        sa.Column("reach", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_metric_snapshots_organization_id", "metric_snapshots", ["organization_id"])
    op.create_index("ix_metric_snapshots_entity_id", "metric_snapshots", ["entity_id"])

    conversion_category = postgresql.ENUM(
        "lead", "qualification", "engagement", "purchase", "subscription", name="conversion_category"
    )
    conversion_category.create(op.get_bind(), checkfirst=True)
    conversion_category_col = postgresql.ENUM(
        "lead", "qualification", "engagement", "purchase", "subscription", name="conversion_category", create_type=False
    )

    op.create_table(
        "conversion_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("category", conversion_category_col, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("counts_as_revenue", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_conversion_types_organization_id", "conversion_types", ["organization_id"])

    op.create_table(
        "conversion_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversion_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value_cents", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("reported_by_source", postgresql.ENUM(name="platform_type", create_type=False), nullable=False),
        sa.Column("converted_entity_type", sa.String(length=50), nullable=True),
        sa.Column("converted_entity_id", sa.String(length=255), nullable=True),
        sa.Column("touchpoints_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversion_type_id"], ["conversion_types.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_conversion_events_organization_id", "conversion_events", ["organization_id"])
    op.create_index("ix_conversion_events_conversion_type_id", "conversion_events", ["conversion_type_id"])

    op.create_table(
        "website_tracking_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("key", name="uq_website_tracking_keys_key"),
    )
    op.create_index("ix_website_tracking_keys_organization_id", "website_tracking_keys", ["organization_id"])
    op.create_index("ix_website_tracking_keys_key", "website_tracking_keys", ["key"])

    website_tracking_event_type = postgresql.ENUM("page_view", "conversion", name="website_tracking_event_type")
    website_tracking_event_type.create(op.get_bind(), checkfirst=True)
    website_tracking_event_type_col = postgresql.ENUM(
        "page_view", "conversion", name="website_tracking_event_type", create_type=False
    )

    op.create_table(
        "website_tracking_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", website_tracking_event_type_col, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("visitor_id", sa.String(length=64), nullable=False),
        sa.Column("page_url", sa.String(length=1000), nullable=True),
        sa.Column("utm_json", sa.JSON(), nullable=False),
        sa.Column("conversion_type_name", sa.String(length=100), nullable=True),
        sa.Column("conversion_value_cents", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_website_tracking_events_organization_id", "website_tracking_events", ["organization_id"])
    op.create_index("ix_website_tracking_events_visitor_id", "website_tracking_events", ["visitor_id"])


def downgrade() -> None:
    op.drop_index("ix_website_tracking_events_visitor_id", table_name="website_tracking_events")
    op.drop_index("ix_website_tracking_events_organization_id", table_name="website_tracking_events")
    op.drop_table("website_tracking_events")
    postgresql.ENUM(name="website_tracking_event_type").drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_website_tracking_keys_key", table_name="website_tracking_keys")
    op.drop_index("ix_website_tracking_keys_organization_id", table_name="website_tracking_keys")
    op.drop_table("website_tracking_keys")

    op.drop_index("ix_conversion_events_conversion_type_id", table_name="conversion_events")
    op.drop_index("ix_conversion_events_organization_id", table_name="conversion_events")
    op.drop_table("conversion_events")

    op.drop_index("ix_conversion_types_organization_id", table_name="conversion_types")
    op.drop_table("conversion_types")
    postgresql.ENUM(name="conversion_category").drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_metric_snapshots_entity_id", table_name="metric_snapshots")
    op.drop_index("ix_metric_snapshots_organization_id", table_name="metric_snapshots")
    op.drop_table("metric_snapshots")
    postgresql.ENUM(name="metric_entity_type").drop(op.get_bind(), checkfirst=True)
