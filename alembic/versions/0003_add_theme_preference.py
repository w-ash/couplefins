"""Add theme_preference to persons.

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "persons",
        sa.Column(
            "theme_preference", sa.String, nullable=False, server_default="system"
        ),
    )


def downgrade() -> None:
    op.drop_column("persons", "theme_preference")
