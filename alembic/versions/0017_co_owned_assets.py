"""Add co_owned_assets: the couple's home and the settings of their shares.

One row per couple: the home's name, the contribution kinds that count
toward the owners' shares (the `share:` tag values), the repair threshold,
and the bank balance last read from the bank with its date. Money and dates
are strings, as elsewhere. No data step: the table starts empty.

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "co_owned_assets",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("repair_threshold", sa.String(), nullable=False),
        sa.Column("qualifying_kinds", postgresql.JSONB(), nullable=False),
        sa.Column("bank_balance", sa.String(), nullable=True),
        sa.Column("bank_balance_as_of", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("co_owned_assets")
