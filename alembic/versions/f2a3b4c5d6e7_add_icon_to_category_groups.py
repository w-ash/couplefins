"""add icon column to category_groups

Revision ID: f2a3b4c5d6e7
Revises: e1f2g3h4i5j6
Create Date: 2026-03-13 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2a3b4c5d6e7"
down_revision: str | Sequence[str] | None = "e1f2g3h4i5j6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Default icons for existing groups
_DEFAULT_ICONS: dict[str, str] = {
    "Income": "wallet",
    "Rent": "key",
    "Home Expenses": "home",
    "Auto & Transport": "car",
    "Food & Dining": "utensils-crossed",
    "Playa": "sun",
    "Shopping": "shopping-bag",
    "Health & Wellness": "heart-pulse",
    "Lifestyle": "music",
    "Travel": "plane",
    "Festivals": "tent",
    "Gifts & Donations": "gift",
    "Financial": "landmark",
    "Other": "package",
    "Work": "briefcase",
    "Transfer": "arrow-left-right",
}


def upgrade() -> None:
    with op.batch_alter_table("category_groups") as batch_op:
        batch_op.add_column(sa.Column("icon", sa.String(), nullable=True))

    # Set default icons for existing groups
    category_groups = sa.table(
        "category_groups",
        sa.column("name", sa.String),
        sa.column("icon", sa.String),
    )
    for name, icon in _DEFAULT_ICONS.items():
        op.execute(
            category_groups
            .update()
            .where(category_groups.c.name == name)
            .values(icon=icon)
        )


def downgrade() -> None:
    with op.batch_alter_table("category_groups") as batch_op:
        batch_op.drop_column("icon")
