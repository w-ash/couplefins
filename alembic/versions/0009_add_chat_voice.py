"""Add chat_voice to persons.

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "persons",
        sa.Column("chat_voice", sa.String, nullable=False, server_default="fiona"),
    )


def downgrade() -> None:
    op.drop_column("persons", "chat_voice")
