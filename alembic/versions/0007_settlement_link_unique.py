"""Add unique constraint on settlement_transaction_links.transaction_id.

Prevents the same transaction from being linked to multiple settlements.

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_stl_transaction_id", table_name="settlement_transaction_links")
    op.create_index(
        "ix_stl_transaction_id",
        "settlement_transaction_links",
        ["transaction_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_stl_transaction_id", table_name="settlement_transaction_links")
    op.create_index(
        "ix_stl_transaction_id",
        "settlement_transaction_links",
        ["transaction_id"],
    )
