"""add occurrence to natural key for duplicate disambiguation

Revision ID: c8a3b2d5e6f7
Revises: b7f2a1c3d4e5
Create Date: 2026-03-10 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8a3b2d5e6f7"
down_revision: str | Sequence[str] | None = "b7f2a1c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.add_column(
            sa.Column("occurrence", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.drop_constraint("uq_transactions_natural_key", type_="unique")
        batch_op.create_unique_constraint(
            "uq_transactions_natural_key",
            [
                "date",
                "amount",
                "account",
                "original_statement",
                "occurrence",
                "payer_person_id",
            ],
        )


def downgrade() -> None:
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.drop_constraint("uq_transactions_natural_key", type_="unique")
        batch_op.create_unique_constraint(
            "uq_transactions_natural_key",
            ["date", "amount", "account", "original_statement", "payer_person_id"],
        )
        batch_op.drop_column("occurrence")
