"""promote category_mappings to categories table with UUID PK and include_personal

Revision ID: i5j6k7l8m9n0
Revises: h4i5j6k7l8m9
Create Date: 2026-03-18 22:00:00.000000

"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "i5j6k7l8m9n0"
down_revision: str | None = "h4i5j6k7l8m9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create new categories table
    op.create_table(
        "categories",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), unique=True, nullable=False),
        sa.Column(
            "group_id",
            sa.String(),
            sa.ForeignKey("category_groups.id"),
            nullable=True,
        ),
        sa.Column(
            "include_personal",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
    )

    # Migrate data from category_mappings → categories (generate UUIDs in Python)
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT category, group_id FROM category_mappings")
    ).fetchall()
    for row in rows:
        conn.execute(
            sa.text(
                "INSERT INTO categories (id, name, group_id, include_personal) "
                "VALUES (:id, :name, :group_id, 0)"
            ),
            {"id": str(uuid4()), "name": row[0], "group_id": row[1]},
        )

    # Drop old table
    op.drop_table("category_mappings")


def downgrade() -> None:
    # Recreate category_mappings
    op.create_table(
        "category_mappings",
        sa.Column("category", sa.String(), primary_key=True),
        sa.Column(
            "group_id",
            sa.String(),
            sa.ForeignKey("category_groups.id"),
            nullable=True,
        ),
    )

    # Migrate data back
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT name, group_id FROM categories")).fetchall()
    for row in rows:
        conn.execute(
            sa.text(
                "INSERT INTO category_mappings (category, group_id) "
                "VALUES (:category, :group_id)"
            ),
            {"category": row[0], "group_id": row[1]},
        )

    # Drop categories table
    op.drop_table("categories")
