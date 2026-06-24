"""shadow triage (status + reviews) and watchlist

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("shadow_findings",
                  sa.Column("status", sa.String(16), server_default="new", nullable=False))
    op.create_index("ix_shadow_findings_status", "shadow_findings", ["status"])

    op.create_table(
        "shadow_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("shadow_findings.id", ondelete="CASCADE")),
        sa.Column("reviewer", sa.String(64)),
        sa.Column("decision", sa.String(16)),
        sa.Column("notes", sa.Text),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_shadow_reviews_finding_id", "shadow_reviews", ["finding_id"])

    op.create_table(
        "shadow_watchlist",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("value", sa.String(256), unique=True),
        sa.Column("kind", sa.String(24)),
        sa.Column("note", sa.Text),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_shadow_watchlist_value", "shadow_watchlist", ["value"])


def downgrade() -> None:
    op.drop_table("shadow_watchlist")
    op.drop_table("shadow_reviews")
    op.drop_index("ix_shadow_findings_status", "shadow_findings")
    op.drop_column("shadow_findings", "status")
