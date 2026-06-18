"""add media_anomalies to analysis_sessions

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("analysis_sessions", sa.Column("media_anomalies", postgresql.JSONB))


def downgrade() -> None:
    op.drop_column("analysis_sessions", "media_anomalies")
