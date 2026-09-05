"""Add the income kind; mark the seeded Income group as income.

`income` joins `expense` and `transfer` as a category group kind: money
coming in (paychecks, dividends). Like transfers, income rows are excluded
from spending, budgets, and settlement but stay visible. Before this, a
person's "My Spending" counted a paycheck as a negative expense.

The data step flips any group named "Income" (the seeded one) and drops its
budgets, the way 0013 did for "Transfer".

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CHECK_NAME = "ck_category_groups_kind"


def upgrade() -> None:
    op.drop_constraint(_CHECK_NAME, "category_groups", type_="check")
    op.create_check_constraint(
        _CHECK_NAME, "category_groups", "kind IN ('expense', 'transfer', 'income')"
    )
    op.execute(
        "DELETE FROM category_group_budgets WHERE group_id IN "
        "(SELECT id FROM category_groups WHERE lower(name) = 'income')"
    )
    op.execute(
        "UPDATE category_groups SET kind = 'income' WHERE lower(name) = 'income'"
    )


def downgrade() -> None:
    op.execute("UPDATE category_groups SET kind = 'expense' WHERE kind = 'income'")
    op.drop_constraint(_CHECK_NAME, "category_groups", type_="check")
    op.create_check_constraint(
        _CHECK_NAME, "category_groups", "kind IN ('expense', 'transfer')"
    )
