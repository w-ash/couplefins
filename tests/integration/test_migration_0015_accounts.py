import uuid

from sqlalchemy import Connection, create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command
from src.config.settings import get_settings
from src.domain.entities.account import personal_account_id
from src.infrastructure.persistence.database.db_connection import (
    alembic_config,
    run_migrations,
)

_ALICE = "aaaaaaaa-0000-0000-0000-000000000001"
_BOB = "bbbbbbbb-0000-0000-0000-000000000002"


def _insert_row(
    conn: Connection, tx_id: str, upload_id: str, payer: str, account: str
) -> None:
    conn.execute(
        text(
            "INSERT INTO transactions (id, upload_id, date, merchant, category, "
            "account, original_statement, occurrence, notes, amount, tags, "
            "household, payer_person_id, payer_percentage, is_settlement, "
            "is_excluded) VALUES (:id, :upload_id, '2026-01-15', 'Shop', "
            "'Groceries', :account, :statement, 0, '', '-10.00', '[]', false, "
            ":payer, 100, false, false)"
        ),
        {
            "id": tx_id,
            "upload_id": upload_id,
            "account": account,
            "statement": tx_id,
            "payer": payer,
        },
    )


async def test_backfill_gives_each_row_a_personal_account_of_its_payer(
    db_session: AsyncSession,  # truncates the tables afterwards
) -> None:
    sync_url = get_settings().database.sync_url
    command.downgrade(alembic_config(sync_url), "0014")
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
            _insert_row(conn, "a1", "upload-Alice", _ALICE, "Chase")
            _insert_row(conn, "a2", "upload-Alice", _ALICE, "Chase")
            _insert_row(conn, "a3", "upload-Alice", _ALICE, "Amex")
            _insert_row(conn, "b1", "upload-Bob", _BOB, "Chase")

        run_migrations(sync_url)

        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT t.id, a.name, a.kind, a.owner_person_id, a.id "
                    "FROM transactions t JOIN accounts a ON a.id = t.account_id "
                    "ORDER BY t.id"
                )
            ).all()
            account_count = conn.execute(text("SELECT count(*) FROM accounts")).scalar()
            uploads = conn.execute(
                text("SELECT DISTINCT importer, content_sha256 FROM uploads")
            ).all()
    finally:
        engine.dispose()

    assert [(r[0], r[1], r[2], r[3]) for r in rows] == [
        ("a1", "Chase", "personal", _ALICE),
        ("a2", "Chase", "personal", _ALICE),
        ("a3", "Amex", "personal", _ALICE),
        ("b1", "Chase", "personal", _BOB),
    ]
    # The ids the app derives, so later imports land in the same accounts.
    alice, bob = uuid.UUID(_ALICE), uuid.UUID(_BOB)
    assert [r[4] for r in rows] == [
        str(personal_account_id(alice, "Chase")),
        str(personal_account_id(alice, "Chase")),
        str(personal_account_id(alice, "Amex")),
        str(personal_account_id(bob, "Chase")),
    ]
    assert account_count == 3
    assert uploads == [("monarch_csv", None)]
