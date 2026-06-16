"""initial: analysis_sessions + analyst_reviews

Revision ID: 0001
Revises:
Create Date: 2026-06-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analysis_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("record_id", sa.String(128)),
        sa.Column("modality", sa.String(16), nullable=False),
        sa.Column("source", sa.String(64)),
        sa.Column("input_url", sa.Text),
        sa.Column("text_preview", sa.Text),
        sa.Column("language", sa.String(8)),
        sa.Column("fraud_type", sa.String(64)),
        sa.Column("label", sa.String(16)),
        sa.Column("risk_score", sa.Integer),
        sa.Column("risk_level", sa.String(16)),
        sa.Column("risk_signals", postgresql.JSONB),
        sa.Column("entities", postgresql.JSONB),
        sa.Column("evidence_spans", postgresql.JSONB),
        sa.Column("recommendation", sa.Text),
        sa.Column("llm_used", sa.Boolean),
        sa.Column("latency_ms", sa.Integer),
    )
    op.create_index("ix_analysis_sessions_created_at", "analysis_sessions", ["created_at"])
    op.create_index("ix_analysis_sessions_risk_level", "analysis_sessions", ["risk_level"])
    op.create_index("ix_analysis_sessions_fraud_type", "analysis_sessions", ["fraud_type"])

    op.create_table(
        "analyst_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("analysis_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer", sa.String(64)),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("final_label", sa.String(16)),
        sa.Column("final_fraud_type", sa.String(64)),
        sa.Column("notes", sa.Text),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_analyst_reviews_session_id", "analyst_reviews", ["session_id"])


def downgrade() -> None:
    op.drop_table("analyst_reviews")
    op.drop_table("analysis_sessions")
