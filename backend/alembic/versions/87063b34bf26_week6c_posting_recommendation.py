"""week 6c: posting_recommendation ai_usage_source value

Revision ID: 87063b34bf26
Revises: 265ad56649a3
Create Date: 2026-10-02

Adds the posting_recommendation value to ai_usage_source (see
app/scheduling/recommendation_service.py). Same ALTER TYPE ... ADD VALUE
pattern used for every prior extension of this enum
(campaign_builder/content_generation/image_analysis in earlier weeks).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "87063b34bf26"
down_revision: Union[str, None] = "265ad56649a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE ai_usage_source ADD VALUE IF NOT EXISTS 'posting_recommendation'")


def downgrade() -> None:
    # Note: PostgreSQL does not support removing a value from an existing
    # enum type - same permanent limitation documented in every prior
    # migration that has extended ai_usage_source or platform_type.
    pass
