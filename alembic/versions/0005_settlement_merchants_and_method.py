"""Add settlement_merchants table and capitalize existing settlement methods.

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-03
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "settlement_merchants",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("merchant_pattern", sa.String, nullable=False),
    )

    op.execute("UPDATE settlements SET method = 'Venmo' WHERE method = 'venmo'")
    op.execute("UPDATE settlements SET method = 'Zelle' WHERE method = 'zelle'")
    op.execute("UPDATE settlements SET method = 'Other' WHERE method = 'other'")
