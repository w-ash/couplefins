"""Settlement portions; drop the year/month annotation.

Every settlement now records exactly which months it covers and with how
much: settlement_portions rows of (year, month, amount) summing to the
settlement amount. Portions drive the ledger math; the old display-only
year/month annotation columns are dropped.

Data migration: each existing settlement becomes one portion carrying its
full amount — into its annotated month when set, else its settled_at month.

Downgrade recreates the annotation columns, backfills each settlement's
(year, month) from its oldest portion, then drops the portions table.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-23
"""

from collections.abc import Sequence
from datetime import datetime
import uuid

import sqlalchemy as sa

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _migrate_portions(conn: sa.Connection) -> None:
    settlements = conn.execute(
        sa.text("SELECT id, year, month, amount, settled_at FROM settlements")
    ).all()
    for row in settlements:
        if row.year is not None and row.month is not None:
            year, month = row.year, row.month
        else:
            settled = datetime.fromisoformat(row.settled_at)
            year, month = settled.year, settled.month
        conn.execute(
            sa.text(
                "INSERT INTO settlement_portions "
                "(id, settlement_id, year, month, amount) "
                "VALUES (:id, :sid, :year, :month, :amount)"
            ),
            {
                "id": str(uuid.uuid4()),
                "sid": row.id,
                "year": year,
                "month": month,
                "amount": row.amount,
            },
        )


def upgrade() -> None:
    op.create_table(
        "settlement_portions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "settlement_id",
            sa.String(),
            sa.ForeignKey("settlements.id"),
            nullable=False,
        ),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("amount", sa.String(), nullable=False),
        sa.UniqueConstraint(
            "settlement_id", "year", "month", name="uq_settlement_portion_period"
        ),
    )
    op.create_index(
        "ix_settlement_portions_year_month", "settlement_portions", ["year", "month"]
    )

    _migrate_portions(op.get_bind())

    op.drop_index("ix_settlements_year_month", table_name="settlements")
    op.drop_column("settlements", "year")
    op.drop_column("settlements", "month")


def downgrade() -> None:
    op.add_column("settlements", sa.Column("year", sa.Integer(), nullable=True))
    op.add_column("settlements", sa.Column("month", sa.Integer(), nullable=True))
    op.create_index("ix_settlements_year_month", "settlements", ["year", "month"])
    # Oldest portion wins as the restored annotation.
    op.get_bind().execute(
        sa.text(
            """
            UPDATE settlements SET (year, month) = (
                SELECT sp.year, sp.month FROM settlement_portions sp
                WHERE sp.settlement_id = settlements.id
                ORDER BY sp.year, sp.month LIMIT 1
            )
            WHERE id IN (SELECT settlement_id FROM settlement_portions)
            """
        )
    )
    op.drop_table("settlement_portions")
