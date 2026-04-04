"""Replace effective_from with year + month on category_group_budgets.

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # No production data — only 1 test budget exists
    op.execute(sa.text("DELETE FROM category_group_budgets"))

    op.drop_constraint(
        "category_group_budgets_group_id_effective_from_person_id_key",
        "category_group_budgets",
        type_="unique",
    )
    op.drop_column("category_group_budgets", "effective_from")

    op.add_column(
        "category_group_budgets",
        sa.Column("year", sa.Integer, nullable=False),
    )
    op.add_column(
        "category_group_budgets",
        sa.Column("month", sa.Integer, nullable=False),
    )

    # Partial unique indexes to handle nullable person_id:
    # PostgreSQL excludes NULLs from regular unique constraints,
    # so two partial indexes are needed.
    op.create_index(
        "uq_budget_group_month_personal",
        "category_group_budgets",
        ["group_id", "year", "month", "person_id"],
        unique=True,
        postgresql_where=text("person_id IS NOT NULL"),
    )
    op.create_index(
        "uq_budget_group_month_household",
        "category_group_budgets",
        ["group_id", "year", "month"],
        unique=True,
        postgresql_where=text("person_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_budget_group_month_household", "category_group_budgets")
    op.drop_index("uq_budget_group_month_personal", "category_group_budgets")
    op.drop_column("category_group_budgets", "month")
    op.drop_column("category_group_budgets", "year")
    op.add_column(
        "category_group_budgets",
        sa.Column("effective_from", sa.String, nullable=False),
    )
    op.create_unique_constraint(
        "category_group_budgets_group_id_effective_from_person_id_key",
        "category_group_budgets",
        ["group_id", "effective_from", "person_id"],
    )
