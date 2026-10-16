import uuid

import pytest
from sqlalchemy import Connection, create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command
from src.config.settings import get_settings
from src.domain.entities.account import joint_account_id, personal_account_id
from src.infrastructure.persistence.database.db_connection import (
    alembic_config,
    run_migrations,
)

_ALICE = "aaaaaaaa-0000-0000-0000-000000000001"
_BOB = "bbbbbbbb-0000-0000-0000-000000000002"
_JOINT_LABEL = "Joint checking"
_JOINT_ACCOUNT = str(joint_account_id(_JOINT_LABEL))

_ROWS_SQL = text("SELECT id, account_id, payer_person_id FROM transactions ORDER BY id")
_KEY_COLUMNS_SQL = text(
    "SELECT a.attname FROM pg_constraint c "
    "CROSS JOIN LATERAL unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord) "
    "JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum "
    "WHERE c.conname = 'uq_transactions_natural_key' ORDER BY k.ord"
)


def _personal_account(person: str, label: str) -> str:
    return str(personal_account_id(uuid.UUID(person), label))


def _insert_account(
    conn: Connection, account_id: str, name: str, owner: str | None
) -> None:
    conn.execute(
        text(
            "INSERT INTO accounts (id, name, kind, owner_person_id) "
            "VALUES (:id, :name, :kind, :owner)"
        ),
        {
            "id": account_id,
            "name": name,
            "kind": "personal" if owner else "joint",
            "owner": owner,
        },
    )


def _insert_row(
    conn: Connection,
    tx_id: str,
    upload_id: str,
    payer: str | None,
    account: str,
    account_id: str,
) -> None:
    conn.execute(
        text(
            "INSERT INTO transactions (id, upload_id, date, merchant, category, "
            "account, account_id, original_statement, occurrence, notes, amount, "
            "tags, household, payer_person_id, payer_percentage, is_settlement, "
            "is_excluded) VALUES (:id, :upload_id, '2026-01-15', 'Shop', "
            "'Groceries', :account, :account_id, 'SHOP', 0, '', '-10.00', '[]', "
            "false, :payer, 100, false, false)"
        ),
        {
            "id": tx_id,
            "upload_id": upload_id,
            "account": account,
            "account_id": account_id,
            "payer": payer,
        },
    )


async def test_joint_rows_migration_keeps_every_row_and_rekeys_the_natural_key(
    db_session: AsyncSession,  # truncates the tables afterwards
) -> None:
    sync_url = get_settings().database.sync_url
    command.downgrade(alembic_config(sync_url), "0015")
    engine = create_engine(sync_url)
    try:
        with engine.begin() as conn:
            for person_id, name in ((_ALICE, "Alice"), (_BOB, "Bob")):
                conn.execute(
                    text("INSERT INTO persons (id, name) VALUES (:id, :name)"),
                    {"id": person_id, "name": name},
                )
                conn.execute(
                    text(
                        "INSERT INTO uploads (id, person_id, filename, uploaded_at) "
                        "VALUES (:id, :person, 'export.csv', '2026-02-01T00:00:00')"
                    ),
                    {"id": f"upload-{name}", "person": person_id},
                )
            alice_chase = _personal_account(_ALICE, "Chase")
            bob_chase = _personal_account(_BOB, "Chase")
            alice_amex = _personal_account(_ALICE, "Amex")
            _insert_account(conn, alice_chase, "Chase", _ALICE)
            _insert_account(conn, bob_chase, "Chase", _BOB)
            _insert_account(conn, alice_amex, "Amex", _ALICE)
            # a1 and b1 share date, amount, label, statement, and occurrence.
            _insert_row(conn, "a1", "upload-Alice", _ALICE, "Chase", alice_chase)
            _insert_row(conn, "b1", "upload-Bob", _BOB, "Chase", bob_chase)
            _insert_row(conn, "a2", "upload-Alice", _ALICE, "Amex", alice_amex)
            before = conn.execute(_ROWS_SQL).all()

        run_migrations(sync_url)

        with engine.begin() as conn:
            assert conn.execute(_ROWS_SQL).all() == before
            assert conn.execute(_KEY_COLUMNS_SQL).scalars().all() == [
                "date",
                "amount",
                "account_id",
                "original_statement",
                "occurrence",
            ]
            columns = dict(
                conn.execute(
                    text(
                        "SELECT column_name, is_nullable "
                        "FROM information_schema.columns "
                        "WHERE table_name = 'transactions' AND column_name IN "
                        "('payer_person_id', 'depositor_person_id', 'owner_shares')"
                    )
                ).all()
            )
            assert columns == {
                "payer_person_id": "YES",
                "depositor_person_id": "YES",
                "owner_shares": "YES",
            }
            _insert_account(conn, _JOINT_ACCOUNT, _JOINT_LABEL, None)
            _insert_row(conn, "j1", "upload-Alice", None, _JOINT_LABEL, _JOINT_ACCOUNT)

        # The same joint row from Bob's export is the same key: rejected.
        with pytest.raises(IntegrityError), engine.begin() as conn:
            _insert_row(conn, "j2", "upload-Bob", None, _JOINT_LABEL, _JOINT_ACCOUNT)

        # Owner shares belong on joint rows only.
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE transactions SET owner_shares = "
                    "'{\"a\": 50, \"b\": 50}'::jsonb WHERE id = 'a1'"
                )
            )

        command.downgrade(alembic_config(sync_url), "0015")

        with engine.connect() as conn:
            assert conn.execute(
                text("SELECT id FROM transactions ORDER BY id")
            ).scalars().all() == ["a1", "a2", "b1"]
            assert conn.execute(_KEY_COLUMNS_SQL).scalars().all() == [
                "date",
                "amount",
                "account",
                "original_statement",
                "occurrence",
                "payer_person_id",
            ]
    finally:
        engine.dispose()
        run_migrations(sync_url)
