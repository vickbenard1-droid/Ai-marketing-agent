"""week 5: brand voice, content engine, SEO content

Revision ID: 62efee233690
Revises: 2e5833d2ae91
Create Date: 2026-09-11

Hand-authored against the SQLAlchemy models, verified the same way as
every prior migration: DDL cross-checked by compiling CreateTable()
against the postgresql dialect for all 4 new tables, and the full
upgrade/downgrade verified via `alembic upgrade/downgrade --sql` (offline
mode) before this file was finalized.

Two parts: (1) adds brand_voice/brand_voice_custom to business_profiles -
this is what creates the `brand_voice` Postgres enum type for the first
time; (2) creates content_assets, content_repurpose_batches, content_items,
seo_content. content_items.brand_voice_used reuses the enum type created
in part 1 (create_type=False) rather than creating a second one - see
app/models/content.py's module docstring for why these intentionally
share one Postgres type.

Table creation order matters here (respecting FK dependencies):
content_assets -> content_repurpose_batches (FK to assets) ->
content_items (FK to both) -> seo_content (FK to content_items).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "62efee233690"
down_revision: Union[str, None] = "2e5833d2ae91"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- extend ai_usage_source (added Week 3, extended Week 4) with the
    # two new Week 5 sources. Same ALTER TYPE ADD VALUE pattern as the
    # Week 4 migration's 'campaign_builder' addition — see that
    # migration's comment for why this must stand alone rather than share
    # a transaction with DDL that might use the new values.
    op.execute("ALTER TYPE ai_usage_source ADD VALUE IF NOT EXISTS 'content_generation'")
    op.execute("ALTER TYPE ai_usage_source ADD VALUE IF NOT EXISTS 'image_analysis'")

    # --- business_profiles: brand voice (creates the brand_voice enum) ---
    brand_voice = postgresql.ENUM(
        "professional",
        "friendly",
        "luxury",
        "educational",
        "funny",
        "bold",
        "inspirational",
        "custom",
        name="brand_voice",
    )
    brand_voice.create(op.get_bind(), checkfirst=True)
    brand_voice_col = postgresql.ENUM(
        "professional",
        "friendly",
        "luxury",
        "educational",
        "funny",
        "bold",
        "inspirational",
        "custom",
        name="brand_voice",
        create_type=False,
    )

    op.add_column("business_profiles", sa.Column("brand_voice", brand_voice_col, nullable=True))
    op.add_column("business_profiles", sa.Column("brand_voice_custom", sa.Text(), nullable=True))

    # --- content_assets ---------------------------------------------------
    asset_type = postgresql.ENUM("image", "video", name="asset_type")
    asset_type.create(op.get_bind(), checkfirst=True)
    asset_type_col = postgresql.ENUM("image", "video", name="asset_type", create_type=False)

    asset_status = postgresql.ENUM("uploaded", "analyzing", "analyzed", "failed", name="asset_status")
    asset_status.create(op.get_bind(), checkfirst=True)
    asset_status_col = postgresql.ENUM(
        "uploaded", "analyzing", "analyzed", "failed", name="asset_status", create_type=False
    )

    op.create_table(
        "content_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("asset_type", asset_type_col, nullable=False),
        sa.Column("status", asset_status_col, nullable=False, server_default="uploaded"),
        sa.Column("original_filename", sa.String(length=500), nullable=False),
        sa.Column("storage_key", sa.String(length=1000), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("ai_description", sa.Text(), nullable=True),
        sa.Column("analysis_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("storage_key", name="uq_content_assets_storage_key"),
    )
    op.create_index("ix_content_assets_organization_id", "content_assets", ["organization_id"])

    # --- content_repurpose_batches -----------------------------------------
    op.create_table(
        "content_repurpose_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("source_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_asset_id"], ["content_assets.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_content_repurpose_batches_organization_id", "content_repurpose_batches", ["organization_id"]
    )

    # --- content_items -------------------------------------------------
    content_type = postgresql.ENUM(
        "facebook_post",
        "instagram_caption",
        "linkedin_post",
        "x_post",
        "tiktok_caption",
        "youtube_title",
        "youtube_description",
        "blog_post",
        "product_description",
        "email",
        "video_script",
        "hook",
        name="content_type",
    )
    content_type.create(op.get_bind(), checkfirst=True)
    content_type_col = postgresql.ENUM(
        "facebook_post",
        "instagram_caption",
        "linkedin_post",
        "x_post",
        "tiktok_caption",
        "youtube_title",
        "youtube_description",
        "blog_post",
        "product_description",
        "email",
        "video_script",
        "hook",
        name="content_type",
        create_type=False,
    )

    content_status = postgresql.ENUM("draft", "approved", name="content_status")
    content_status.create(op.get_bind(), checkfirst=True)
    content_status_col = postgresql.ENUM("draft", "approved", name="content_status", create_type=False)

    # Reuses the brand_voice enum type created above for business_profiles
    # - create_type=False so this doesn't attempt to create it again.
    brand_voice_content_col = postgresql.ENUM(
        "professional",
        "friendly",
        "luxury",
        "educational",
        "funny",
        "bold",
        "inspirational",
        "custom",
        name="brand_voice",
        create_type=False,
    )

    op.create_table(
        "content_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content_type", content_type_col, nullable=False),
        sa.Column("status", content_status_col, nullable=False, server_default="draft"),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("source_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("brand_voice_used", brand_voice_content_col, nullable=True),
        sa.Column("repurpose_batch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_asset_id"], ["content_assets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["repurpose_batch_id"], ["content_repurpose_batches.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("ix_content_items_organization_id", "content_items", ["organization_id"])

    # --- seo_content ------------------------------------------------------
    op.create_table(
        "seo_content",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("topic", sa.String(length=500), nullable=False),
        sa.Column("primary_keyword", sa.String(length=255), nullable=True),
        sa.Column("secondary_keywords", postgresql.ARRAY(sa.String(length=50)), nullable=True),
        sa.Column("search_intent", sa.String(length=100), nullable=True),
        sa.Column("seo_title", sa.String(length=255), nullable=True),
        sa.Column("meta_description", sa.String(length=500), nullable=True),
        sa.Column("url_slug", sa.String(length=255), nullable=True),
        sa.Column("h1", sa.String(length=255), nullable=True),
        sa.Column("h2_structure", postgresql.ARRAY(sa.String(length=50)), nullable=True),
        sa.Column("internal_linking_suggestions", postgresql.ARRAY(sa.String(length=50)), nullable=True),
        sa.Column("image_alt_text", sa.String(length=255), nullable=True),
        sa.Column("hashtags", postgresql.ARRAY(sa.String(length=50)), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("content_id", name="uq_seo_content_content_id"),
    )
    op.create_index("ix_seo_content_organization_id", "seo_content", ["organization_id"])
    op.create_index("ix_seo_content_content_id", "seo_content", ["content_id"])


def downgrade() -> None:
    # Note: PostgreSQL cannot remove enum values (no ALTER TYPE ... DROP
    # VALUE) — 'content_generation' and 'image_analysis' added to
    # ai_usage_source in upgrade() are not removed here, same permanent
    # limitation documented in the Week 4 migration for 'campaign_builder'.

    op.drop_index("ix_seo_content_content_id", table_name="seo_content")
    op.drop_index("ix_seo_content_organization_id", table_name="seo_content")
    op.drop_table("seo_content")

    op.drop_index("ix_content_items_organization_id", table_name="content_items")
    op.drop_table("content_items")
    postgresql.ENUM(name="content_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="content_type").drop(op.get_bind(), checkfirst=True)

    op.drop_index(
        "ix_content_repurpose_batches_organization_id", table_name="content_repurpose_batches"
    )
    op.drop_table("content_repurpose_batches")

    op.drop_index("ix_content_assets_organization_id", table_name="content_assets")
    op.drop_table("content_assets")
    postgresql.ENUM(name="asset_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="asset_type").drop(op.get_bind(), checkfirst=True)

    op.drop_column("business_profiles", "brand_voice_custom")
    op.drop_column("business_profiles", "brand_voice")
    # brand_voice enum type is dropped last, after both columns that use
    # it (business_profiles.brand_voice and content_items.brand_voice_used
    # - the latter already gone via the content_items table drop above)
    # are gone.
    postgresql.ENUM(name="brand_voice").drop(op.get_bind(), checkfirst=True)
