"""idempotent uploads: drop period fields, add natural key constraint

Revision ID: b7f2a1c3d4e5
Revises: 9e733c929b4e
Create Date: 2026-03-10 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7f2a1c3d4e5"
down_revision: str | Sequence[str] | None = "9e733c929b4e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # SQLite requires batch mode for ALTER TABLE
    with op.batch_alter_table("uploads") as batch_op:
        batch_op.drop_column("period_year")
        batch_op.drop_column("period_month")

    # Add natural key unique constraint + person/date index to transactions
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.create_unique_constraint(
            "uq_transactions_natural_key",
            ["date", "amount", "account", "original_statement", "payer_person_id"],
        )
        batch_op.create_index(
            "ix_transactions_person_date", ["payer_person_id", "date"]
        )


def downgrade() -> None:
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.drop_index("ix_transactions_person_date")
        batch_op.drop_constraint("uq_transactions_natural_key", type_="unique")

    with op.batch_alter_table("uploads") as batch_op:
        batch_op.add_column(
            sa.Column("period_year", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("period_month", sa.Integer(), nullable=False, server_default="0")
        )
