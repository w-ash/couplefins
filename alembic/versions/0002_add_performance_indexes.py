"""Add performance indexes.

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_transactions_non_settlement_date",
        "transactions",
        ["household", "date"],
        postgresql_where=sa.text("NOT is_settlement"),
    )
    op.create_index(
        "ix_settlements_year_month",
        "settlements",
        ["year", "month"],
    )


def downgrade() -> None:
    op.drop_index("ix_settlements_year_month", table_name="settlements")
    op.drop_index("ix_transactions_non_settlement_date", table_name="transactions")
