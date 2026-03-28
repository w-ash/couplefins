"""Initial PostgreSQL schema.

Revision ID: 0001
Revises:
Create Date: 2026-03-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Independent tables (no foreign keys) ---

    op.create_table(
        "persons",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("adjustment_account", sa.String, nullable=False, server_default=""),
        sa.Column("password_hash", sa.String, nullable=False, server_default=""),
    )

    op.create_table(
        "category_groups",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("name", sa.String, unique=True, nullable=False),
        sa.Column("icon", sa.String, nullable=True),
    )

    op.create_table(
        "reconciliation_periods",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("month", sa.Integer, nullable=False),
        sa.Column("is_finalized", sa.Boolean, nullable=False),
        sa.Column("finalized_at", sa.String, nullable=True),
        sa.Column("notes", sa.String, nullable=False),
        sa.Column("created_at", sa.String, nullable=False),
        sa.UniqueConstraint("year", "month"),
    )

    # --- Tables with one level of FK dependency ---

    op.create_table(
        "uploads",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("person_id", sa.String, sa.ForeignKey("persons.id"), nullable=False),
        sa.Column("filename", sa.String, nullable=False),
        sa.Column("uploaded_at", sa.String, nullable=False),
    )

    op.create_table(
        "categories",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("name", sa.String, unique=True, nullable=False),
        sa.Column(
            "group_id",
            sa.String,
            sa.ForeignKey("category_groups.id"),
            nullable=True,
        ),
        sa.Column(
            "include_personal",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.create_table(
        "category_group_budgets",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column(
            "group_id",
            sa.String,
            sa.ForeignKey("category_groups.id"),
            nullable=False,
        ),
        sa.Column("monthly_amount", sa.String, nullable=False),
        sa.Column("effective_from", sa.String, nullable=False),
        sa.Column(
            "person_id",
            sa.String,
            sa.ForeignKey("persons.id"),
            nullable=True,
        ),
        sa.UniqueConstraint("group_id", "effective_from", "person_id"),
    )

    op.create_table(
        "settlements",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("month", sa.Integer, nullable=False),
        sa.Column("amount", sa.String, nullable=False),
        sa.Column(
            "from_person_id",
            sa.String,
            sa.ForeignKey("persons.id"),
            nullable=False,
        ),
        sa.Column(
            "to_person_id",
            sa.String,
            sa.ForeignKey("persons.id"),
            nullable=False,
        ),
        sa.Column("method", sa.String, nullable=True),
        sa.Column(
            "is_waived", sa.Boolean, nullable=False, server_default=sa.text("false")
        ),
        sa.Column("notes", sa.String, nullable=False, server_default=""),
        sa.Column("settled_at", sa.String, nullable=False),
        sa.Column("created_at", sa.String, nullable=False),
        sa.UniqueConstraint(
            "year",
            "month",
            "from_person_id",
            "settled_at",
            name="uq_settlements_period_person_time",
        ),
    )

    # --- Transactions (FK → uploads, persons) ---

    op.create_table(
        "transactions",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("upload_id", sa.String, sa.ForeignKey("uploads.id"), nullable=False),
        sa.Column("date", sa.String, nullable=False),
        sa.Column("merchant", sa.String, nullable=False),
        sa.Column("category", sa.String, nullable=False),
        sa.Column("account", sa.String, nullable=False),
        sa.Column("original_statement", sa.String, nullable=False),
        sa.Column("occurrence", sa.Integer, nullable=False, server_default="0"),
        sa.Column("notes", sa.String, nullable=False),
        sa.Column("amount", sa.String, nullable=False),
        sa.Column("tags", postgresql.JSONB, nullable=False),
        sa.Column(
            "household", sa.Boolean, nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "payer_person_id",
            sa.String,
            sa.ForeignKey("persons.id"),
            nullable=False,
        ),
        sa.Column("payer_percentage", sa.Integer, nullable=False, server_default="100"),
        sa.Column(
            "is_settlement", sa.Boolean, nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "is_excluded", sa.Boolean, nullable=False, server_default=sa.text("false")
        ),
        sa.Column("original_date", sa.String, nullable=True),
        sa.Column("original_amount", sa.String, nullable=True),
        sa.UniqueConstraint(
            "date",
            "amount",
            "account",
            "original_statement",
            "occurrence",
            "payer_person_id",
            name="uq_transactions_natural_key",
        ),
        sa.Index("ix_transactions_household_date", "household", "date"),
        sa.Index("ix_transactions_upload_id", "upload_id"),
        sa.Index("ix_transactions_person_date", "payer_person_id", "date"),
        sa.Index("ix_transactions_tags_gin", "tags", postgresql_using="gin"),
    )

    # --- Junction / audit tables (FK → transactions, settlements) ---

    op.create_table(
        "settlement_transaction_links",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column(
            "settlement_id",
            sa.String,
            sa.ForeignKey("settlements.id"),
            nullable=False,
        ),
        sa.Column(
            "transaction_id",
            sa.String,
            sa.ForeignKey("transactions.id"),
            nullable=False,
        ),
        sa.Index("ix_stl_settlement_id", "settlement_id"),
        sa.Index("ix_stl_transaction_id", "transaction_id"),
    )

    op.create_table(
        "transaction_edits",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column(
            "transaction_id",
            sa.String,
            sa.ForeignKey("transactions.id"),
            nullable=False,
        ),
        sa.Column("field_name", sa.String, nullable=False),
        sa.Column("old_value", sa.String, nullable=False),
        sa.Column("new_value", sa.String, nullable=False),
        sa.Column("edited_at", sa.String, nullable=False),
        sa.Index("ix_transaction_edits_transaction_id", "transaction_id"),
    )


def downgrade() -> None:
    op.drop_table("transaction_edits")
    op.drop_table("settlement_transaction_links")
    op.drop_table("transactions")
    op.drop_table("settlements")
    op.drop_table("category_group_budgets")
    op.drop_table("categories")
    op.drop_table("uploads")
    op.drop_table("reconciliation_periods")
    op.drop_table("category_groups")
    op.drop_table("persons")
