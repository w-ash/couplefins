"""Add kind to category_groups; mark existing Transfer groups as transfers.

A group's kind says what its rows mean for the money math: `expense`
(spending) or `transfer` (money movement between the couple's own
accounts — credit card payments, account transfers). Monarch's CSV export
drops its category type, so the app re-declares it on the group. Transfer
rows are excluded from spending, budgets, and settlement but stay visible.

The data step flips any group named "Transfer" (the seeded one) so
existing installs stop counting credit card payments as spending on deploy.
Its budgets go with it: transfer groups carry no budget, and a row left
behind would be invisible on the Budget page yet still copied forward.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CHECK_NAME = "ck_category_groups_kind"


def upgrade() -> None:
    op.add_column(
        "category_groups",
        sa.Column("kind", sa.String(), nullable=False, server_default="expense"),
    )
    op.create_check_constraint(
        _CHECK_NAME, "category_groups", "kind IN ('expense', 'transfer')"
    )
    op.execute(
        "DELETE FROM category_group_budgets WHERE group_id IN "
        "(SELECT id FROM category_groups WHERE lower(name) = 'transfer')"
    )
    op.execute(
        "UPDATE category_groups SET kind = 'transfer' WHERE lower(name) = 'transfer'"
    )


def downgrade() -> None:
    op.drop_constraint(_CHECK_NAME, "category_groups", type_="check")
    op.drop_column("category_groups", "kind")
