"""Add accounts; give every transaction one; record each upload's importer and hash.

An account is personal (one owner) or joint (both owners, no single owner).
Every existing row came from a Monarch export, so the data step creates one
personal account per uploader per Monarch account label and points each row
at it. No figure moves: settlement and spending read the same rows as before.

An upload now records which importer read it and the SHA-256 of the file, so
the same file is never imported twice. Uploads made before this have no hash.

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column(
            "owner_person_id",
            sa.String(),
            sa.ForeignKey("persons.id"),
            nullable=True,
        ),
        sa.UniqueConstraint("owner_person_id", "name", name="uq_accounts_owner_name"),
        sa.CheckConstraint(
            "(kind = 'personal') = (owner_person_id IS NOT NULL)",
            name="ck_accounts_kind_owner",
        ),
    )
    op.execute(
        "INSERT INTO accounts (id, name, kind, owner_person_id) "
        "SELECT gen_random_uuid()::text, account, 'personal', payer_person_id "
        "FROM (SELECT DISTINCT payer_person_id, account FROM transactions) AS labels"
    )

    op.add_column("transactions", sa.Column("account_id", sa.String(), nullable=True))
    op.execute(
        "UPDATE transactions SET account_id = accounts.id FROM accounts "
        "WHERE accounts.owner_person_id = transactions.payer_person_id "
        "AND accounts.name = transactions.account"
    )
    op.alter_column("transactions", "account_id", nullable=False)
    op.create_foreign_key(
        "transactions_account_id_fkey",
        "transactions",
        "accounts",
        ["account_id"],
        ["id"],
    )
    op.create_index("ix_transactions_account_id", "transactions", ["account_id"])

    op.add_column(
        "uploads",
        sa.Column(
            "importer", sa.String(), nullable=False, server_default="monarch_csv"
        ),
    )
    op.add_column("uploads", sa.Column("content_sha256", sa.String(), nullable=True))
    op.create_index(
        "uq_uploads_content_sha256",
        "uploads",
        ["content_sha256"],
        unique=True,
        postgresql_where=sa.text("content_sha256 IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_uploads_content_sha256", table_name="uploads")
    op.drop_column("uploads", "content_sha256")
    op.drop_column("uploads", "importer")
    op.drop_index("ix_transactions_account_id", table_name="transactions")
    op.drop_constraint(
        "transactions_account_id_fkey", "transactions", type_="foreignkey"
    )
    op.drop_column("transactions", "account_id")
    op.drop_table("accounts")
