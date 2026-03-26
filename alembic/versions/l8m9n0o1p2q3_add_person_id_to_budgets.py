"""add person_id to category_group_budgets

Revision ID: l8m9n0o1p2q3
Revises: k7l8m9n0o1p2
Create Date: 2026-03-25 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "l8m9n0o1p2q3"
down_revision: str | None = "k7l8m9n0o1p2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("category_group_budgets", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("person_id", sa.String(), nullable=True))
        batch_op.create_foreign_key(
            "fk_budget_person_id", "persons", ["person_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("category_group_budgets", recreate="always") as batch_op:
        batch_op.drop_column("person_id")
