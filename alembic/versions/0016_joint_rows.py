"""Allow joint rows: a transaction with no payer, keyed by its account.

A joint account's row was paid from both owners' money, so it has no payer.
`payer_person_id` becomes nullable, and the natural key swaps the payer and
the account label for the account id. Every existing row's account id is
uuid5(payer, label), so the old key determines the new one: no row changes
identity, and two owners' rows with the same label stay distinct because
their accounts differ. Both owners' exports of a joint row share one account
id, so they dedup to one row.

A joint row may name its depositor (whose deposit an incoming row is) and
override the owners' 50/50 split with `owner_shares`. Check constraints keep
both on joint rows only.

The downgrade is lossy: it deletes every joint row, with its edits and
settlement links, since the old schema cannot hold a row without a payer.

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NATURAL_KEY = "uq_transactions_natural_key"
_OLD_KEY_COLUMNS = [
    "date",
    "amount",
    "account",
    "original_statement",
    "occurrence",
    "payer_person_id",
]
_NEW_KEY_COLUMNS = ["date", "amount", "account_id", "original_statement", "occurrence"]
_DEPOSITOR_FK = "fk_transactions_depositor_person"
_OWNER_SHARES_CHECK = "ck_transactions_owner_shares_joint_only"
_DEPOSITOR_CHECK = "ck_transactions_depositor_joint_only"


def upgrade() -> None:
    op.drop_constraint(_NATURAL_KEY, "transactions", type_="unique")
    op.create_unique_constraint(_NATURAL_KEY, "transactions", _NEW_KEY_COLUMNS)
    op.alter_column(
        "transactions", "payer_person_id", existing_type=sa.String(), nullable=True
    )

    op.add_column(
        "transactions", sa.Column("depositor_person_id", sa.String(), nullable=True)
    )
    op.create_foreign_key(
        _DEPOSITOR_FK, "transactions", "persons", ["depositor_person_id"], ["id"]
    )
    op.add_column(
        "transactions",
        sa.Column("owner_shares", postgresql.JSONB(), nullable=True),
    )
    op.create_check_constraint(
        _OWNER_SHARES_CHECK,
        "transactions",
        "owner_shares IS NULL OR payer_person_id IS NULL",
    )
    op.create_check_constraint(
        _DEPOSITOR_CHECK,
        "transactions",
        "depositor_person_id IS NULL OR payer_person_id IS NULL",
    )


def downgrade() -> None:
    # Lossy: the old schema has no room for a row without a payer.
    op.execute(
        "DELETE FROM transaction_edits WHERE transaction_id IN "
        "(SELECT id FROM transactions WHERE payer_person_id IS NULL)"
    )
    op.execute(
        "DELETE FROM settlement_transaction_links WHERE transaction_id IN "
        "(SELECT id FROM transactions WHERE payer_person_id IS NULL)"
    )
    op.execute("DELETE FROM transactions WHERE payer_person_id IS NULL")

    op.drop_constraint(_DEPOSITOR_CHECK, "transactions", type_="check")
    op.drop_constraint(_OWNER_SHARES_CHECK, "transactions", type_="check")
    op.drop_column("transactions", "owner_shares")
    op.drop_constraint(_DEPOSITOR_FK, "transactions", type_="foreignkey")
    op.drop_column("transactions", "depositor_person_id")

    op.alter_column(
        "transactions", "payer_person_id", existing_type=sa.String(), nullable=False
    )
    op.drop_constraint(_NATURAL_KEY, "transactions", type_="unique")
    op.create_unique_constraint(_NATURAL_KEY, "transactions", _OLD_KEY_COLUMNS)
