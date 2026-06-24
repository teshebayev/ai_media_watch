"""add shadow_findings table (Digital Shadow)

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shadow_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("item_id", sa.String(128)),
        sa.Column("source_type", sa.String(16)),
        sa.Column("source_url", sa.Text),
        sa.Column("platform", sa.String(64)),
        sa.Column("language", sa.String(8)),
        sa.Column("category", sa.String(32)),
        sa.Column("risk_score", sa.Integer),
        sa.Column("risk_level", sa.String(16)),
        sa.Column("priority", sa.String(16)),
        sa.Column("threat_score", sa.Float),
        sa.Column("signals", postgresql.JSONB),
        sa.Column("entities", postgresql.JSONB),
        sa.Column("wallet_risks", postgresql.JSONB),
        sa.Column("text_preview", sa.Text),
    )
    op.create_index("ix_shadow_findings_created_at", "shadow_findings", ["created_at"])
    op.create_index("ix_shadow_findings_category", "shadow_findings", ["category"])
    op.create_index("ix_shadow_findings_risk_level", "shadow_findings", ["risk_level"])
    op.create_index("ix_shadow_findings_priority", "shadow_findings", ["priority"])
    op.create_index("ix_shadow_findings_source_type", "shadow_findings", ["source_type"])


def downgrade() -> None:
    op.drop_table("shadow_findings")
