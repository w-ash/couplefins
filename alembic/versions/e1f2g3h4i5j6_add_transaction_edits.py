"""add original_date/original_amount to transactions, create transaction_edits table

Revision ID: e1f2g3h4i5j6
Revises: d9e4f5a6b7c8
Create Date: 2026-03-12 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1f2g3h4i5j6"
down_revision: str | Sequence[str] | None = "d9e4f5a6b7c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.add_column(sa.Column("original_date", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("original_amount", sa.String(), nullable=True))

    op.create_table(
        "transaction_edits",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "transaction_id",
            sa.String(),
            sa.ForeignKey("transactions.id"),
            nullable=False,
        ),
        sa.Column("field_name", sa.String(), nullable=False),
        sa.Column("old_value", sa.String(), nullable=False),
        sa.Column("new_value", sa.String(), nullable=False),
        sa.Column("edited_at", sa.String(), nullable=False),
    )
    op.create_index(
        "ix_transaction_edits_transaction_id",
        "transaction_edits",
        ["transaction_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_transaction_edits_transaction_id", "transaction_edits")
    op.drop_table("transaction_edits")

    with op.batch_alter_table("transactions") as batch_op:
        batch_op.drop_column("original_amount")
        batch_op.drop_column("original_date")
