"""Cascade settlement_portions on settlement delete; drop unused index.

Recreates the settlement_portions.settlement_id foreign key with
ondelete=CASCADE so orphan portions cannot survive a settlement delete.
The app-level delete in DeleteSettlementUseCase stays as belt-and-braces.

Also drops ix_settlement_portions_year_month — no query filters portions
by (year, month), and the dataset (two people) needs no index anyway.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-23
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FK_NAME = "settlement_portions_settlement_id_fkey"


def upgrade() -> None:
    op.drop_constraint(_FK_NAME, "settlement_portions", type_="foreignkey")
    op.create_foreign_key(
        _FK_NAME,
        "settlement_portions",
        "settlements",
        ["settlement_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_index("ix_settlement_portions_year_month", table_name="settlement_portions")


def downgrade() -> None:
    op.create_index(
        "ix_settlement_portions_year_month", "settlement_portions", ["year", "month"]
    )
    op.drop_constraint(_FK_NAME, "settlement_portions", type_="foreignkey")
    op.create_foreign_key(
        _FK_NAME,
        "settlement_portions",
        "settlements",
        ["settlement_id"],
        ["id"],
    )
