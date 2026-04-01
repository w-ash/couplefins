"""Normalize all tags to lowercase.

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-31
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        UPDATE transactions
        SET tags = (
            SELECT jsonb_agg(lower(elem))
            FROM jsonb_array_elements_text(tags) AS elem
        )
        WHERE tags != (
            SELECT jsonb_agg(lower(elem))
            FROM jsonb_array_elements_text(tags) AS elem
        )
    """)


def downgrade() -> None:
    pass
