"""rename is_shared to household, make payer_percentage non-nullable

Revision ID: h4i5j6k7l8m9
Revises: g3h4i5j6k7l8
Create Date: 2026-03-18 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "h4i5j6k7l8m9"
down_revision: str | None = "g3h4i5j6k7l8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Backfill NULL payer_percentage before adding NOT NULL constraint
    op.execute(
        "UPDATE transactions SET payer_percentage = 100 WHERE payer_percentage IS NULL"
    )

    # Drop old index before batch alter (avoids column name mismatch)
    op.drop_index("ix_transactions_shared_date", table_name="transactions")

    # SQLite requires batch_alter_table for column rename + alter
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.alter_column("is_shared", new_column_name="household")
        batch_op.alter_column(
            "payer_percentage",
            existing_type=sa.Integer(),
            nullable=False,
            server_default=sa.text("100"),
        )

    # Create new index after rename is complete
    op.create_index(
        "ix_transactions_household_date", "transactions", ["household", "date"]
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_household_date", table_name="transactions")

    with op.batch_alter_table("transactions") as batch_op:
        batch_op.alter_column("household", new_column_name="is_shared")
        batch_op.alter_column(
            "payer_percentage",
            existing_type=sa.Integer(),
            nullable=True,
            server_default=None,
        )

    op.create_index(
        "ix_transactions_shared_date", "transactions", ["is_shared", "date"]
    )

    # Restore NULL for personal transactions (payer_percentage=100 without household)
    op.execute(
        "UPDATE transactions SET payer_percentage = NULL "
        "WHERE is_shared = 0 AND payer_percentage = 100"
    )
