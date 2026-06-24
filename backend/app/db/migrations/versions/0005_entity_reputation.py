"""shadow entity reputation (flywheel: решения аналитика → скоринг)

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-24
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shadow_entity_reputation",
        sa.Column("value", sa.String(256), primary_key=True),
        sa.Column("kind", sa.String(24)),
        sa.Column("abuse_count", sa.Integer, server_default="0", nullable=False),
        sa.Column("confirmed_count", sa.Integer, server_default="0", nullable=False),
        sa.Column("dismissed_count", sa.Integer, server_default="0", nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_shadow_entity_reputation_abuse", "shadow_entity_reputation", ["abuse_count"])


def downgrade() -> None:
    op.drop_index("ix_shadow_entity_reputation_abuse", "shadow_entity_reputation")
    op.drop_table("shadow_entity_reputation")
