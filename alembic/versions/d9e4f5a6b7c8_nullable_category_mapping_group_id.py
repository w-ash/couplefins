"""make category_mapping group_id nullable for unmapped categories

Revision ID: d9e4f5a6b7c8
Revises: c8a3b2d5e6f7
Create Date: 2026-03-10 20:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d9e4f5a6b7c8"
down_revision: str | Sequence[str] | None = "c8a3b2d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("category_mappings") as batch_op:
        batch_op.alter_column("group_id", nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("category_mappings") as batch_op:
        batch_op.alter_column("group_id", nullable=False)
