"""Add edited_by_person_id to transaction_edits.

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-07
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transaction_edits",
        sa.Column(
            "edited_by_person_id",
            sa.String,
            sa.ForeignKey("persons.id"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("transaction_edits", "edited_by_person_id")
