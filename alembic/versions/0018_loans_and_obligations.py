"""Add loans and obligations: the home's loans and what comes due on it.

A loan keeps the terms it was taken out on; a refinance adds the replacing
loan and points the old one at it. Its `slug` links payment rows tagged
`loan:<slug>`. An obligation is a payment due, optionally for a loan, and
names the row that paid it; deleting that row leaves the obligation unpaid.
Obligations are indexed by asset and due date, by loan, and by paying row.
Money and dates are strings, as elsewhere. No data step: both tables start
empty.

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "loans",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "asset_id",
            sa.String(),
            sa.ForeignKey("co_owned_assets.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False, unique=True),
        sa.Column("lender", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("principal", sa.String(), nullable=False),
        sa.Column("annual_rate", sa.String(), nullable=False),
        sa.Column("payment", sa.String(), nullable=False),
        sa.Column("term_months", sa.Integer(), nullable=True),
        sa.Column("first_due_on", sa.String(), nullable=False),
        sa.Column("statement_balance", sa.String(), nullable=False),
        sa.Column("statement_balance_as_of", sa.String(), nullable=False),
        sa.Column(
            "replaced_by_loan_id",
            sa.String(),
            sa.ForeignKey("loans.id"),
            nullable=True,
        ),
        sa.Column("closed_on", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=False, server_default=""),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('interest_only', 'amortizing')", name="ck_loans_kind"
        ),
    )
    op.create_table(
        "obligations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "asset_id",
            sa.String(),
            sa.ForeignKey("co_owned_assets.id"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("amount", sa.String(), nullable=False),
        sa.Column("is_estimate", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("due_on", sa.String(), nullable=False),
        sa.Column("late_after", sa.String(), nullable=True),
        sa.Column("pays_from", sa.String(), nullable=True),
        sa.Column("loan_id", sa.String(), sa.ForeignKey("loans.id"), nullable=True),
        sa.Column(
            "paid_by_transaction_id",
            sa.String(),
            sa.ForeignKey("transactions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notes", sa.String(), nullable=False, server_default=""),
        sa.CheckConstraint(
            "kind IN ('loan_payment', 'property_tax', 'insurance', 'other')",
            name="ck_obligations_kind",
        ),
    )
    op.create_index("ix_obligations_asset_due", "obligations", ["asset_id", "due_on"])
    op.create_index("ix_obligations_loan_id", "obligations", ["loan_id"])
    op.create_index(
        "ix_obligations_paid_by_transaction_id",
        "obligations",
        ["paid_by_transaction_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_obligations_paid_by_transaction_id", table_name="obligations")
    op.drop_index("ix_obligations_loan_id", table_name="obligations")
    op.drop_index("ix_obligations_asset_due", table_name="obligations")
    op.drop_table("obligations")
    op.drop_table("loans")
