"""Make settlement year/month nullable annotations; drop period unique constraint.

The v1.7.5 settlement ledger nets everything all-time — a settlement's
year/month becomes optional "recorded against" display metadata, and one
payment may cover many months, so the one-settlement-per-(period, person,
time) constraint no longer applies.

Downgrade backfills year/month from the ISO settled_at string for NULL rows,
restores NOT NULL, then recreates the unique constraint. The recreate can
fail if duplicate (year, month, from_person_id, settled_at) rows were created
while the constraint was absent — accepted, best-effort downgrade.

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-04
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("settlements", "year", existing_type=sa.Integer(), nullable=True)
    op.alter_column("settlements", "month", existing_type=sa.Integer(), nullable=True)
    op.drop_constraint(
        "uq_settlements_period_person_time", "settlements", type_="unique"
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE settlements
        SET year = CAST(SUBSTRING(settled_at FROM 1 FOR 4) AS INTEGER),
            month = CAST(SUBSTRING(settled_at FROM 6 FOR 2) AS INTEGER)
        WHERE year IS NULL OR month IS NULL
        """
    )
    op.alter_column("settlements", "year", existing_type=sa.Integer(), nullable=False)
    op.alter_column("settlements", "month", existing_type=sa.Integer(), nullable=False)
    op.create_unique_constraint(
        "uq_settlements_period_person_time",
        "settlements",
        ["year", "month", "from_person_id", "settled_at"],
    )
