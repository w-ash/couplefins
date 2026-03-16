"""add settlements tables and is_settlement to transactions

Revision ID: g3h4i5j6k7l8
Revises: f2a3b4c5d6e7
Create Date: 2026-03-13 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g3h4i5j6k7l8"
down_revision: str | Sequence[str] | None = "f2a3b4c5d6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.add_column(
            sa.Column("is_settlement", sa.Boolean(), nullable=False, server_default="0")
        )

    op.create_table(
        "settlements",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("amount", sa.String(), nullable=False),
        sa.Column(
            "from_person_id",
            sa.String(),
            sa.ForeignKey("persons.id"),
            nullable=False,
        ),
        sa.Column(
            "to_person_id",
            sa.String(),
            sa.ForeignKey("persons.id"),
            nullable=False,
        ),
        sa.Column("method", sa.String(), nullable=True),
        sa.Column("is_waived", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("notes", sa.String(), nullable=False, server_default=""),
        sa.Column("settled_at", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.UniqueConstraint(
            "year",
            "month",
            "from_person_id",
            "settled_at",
            name="uq_settlements_period_person_time",
        ),
    )

    op.create_table(
        "settlement_transaction_links",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "settlement_id",
            sa.String(),
            sa.ForeignKey("settlements.id"),
            nullable=False,
        ),
        sa.Column(
            "transaction_id",
            sa.String(),
            sa.ForeignKey("transactions.id"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_settlements_year_month",
        "settlements",
        ["year", "month"],
    )
    op.create_index(
        "ix_stl_settlement_id",
        "settlement_transaction_links",
        ["settlement_id"],
    )
    op.create_index(
        "ix_stl_transaction_id",
        "settlement_transaction_links",
        ["transaction_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_stl_transaction_id", "settlement_transaction_links")
    op.drop_index("ix_stl_settlement_id", "settlement_transaction_links")
    op.drop_table("settlement_transaction_links")
    op.drop_index("ix_settlements_year_month", "settlements")
    op.drop_table("settlements")

    with op.batch_alter_table("transactions") as batch_op:
        batch_op.drop_column("is_settlement")
